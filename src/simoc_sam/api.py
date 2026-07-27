"""Read-only Flask API for the lightweight sensor frontend.

Serves data written to SQLite by the sqlwriter.  Uses its own dedicated
read connection (WAL mode allows safe concurrent reads with the writer).
"""

import io
import csv
import json
import logging
import time
import pathlib
import sqlite3

from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request, g, Response
from werkzeug.exceptions import HTTPException

from simoc_sam import config, db
from simoc_sam.sensors.utils import SENSOR_DATA


# in production nginx serves the frontend and proxies /api to Flask;
# serving it from Flask too allows running without nginx during development
FRONTEND_DIR = pathlib.Path(__file__).resolve().parents[2] / 'frontend'


def parse_timestamp(ts):
    """Parse an ISO timestamp string, assuming UTC if naive."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_unix_ms(ts):
    """Convert an ISO timestamp string to Unix milliseconds."""
    return int(parse_timestamp(ts).timestamp() * 1000)


def create_app(db_path=None):
    """Create and return the Flask app (db_path overrides config.db_path)."""
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
    app.config['DB_PATH'] = db_path or config.db_path

    # When running under Gunicorn, inherit its log handlers and level so
    # app.logger messages appear in journalctl alongside Gunicorn's own logs.
    gunicorn_logger = logging.getLogger('gunicorn.error')
    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    @app.get('/')
    def index():
        return app.send_static_file('index.html')

    def get_db():
        """Return a per-request read connection to the SQLite DB."""
        if 'db_conn' not in g:
            g.db_conn = db.connect(app.config['DB_PATH'])
        return g.db_conn

    @app.teardown_appcontext
    def close_conn(exception):
        conn = g.pop('db_conn', None)
        if conn is not None:
            conn.close()

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        if isinstance(err, HTTPException):
            return err  # let Flask handle 4xx/5xx HTTP errors normally
        app.logger.exception('Unhandled exception')
        return jsonify({'error': 'Internal server error'}), 500

    def parse_selection(payload):
        """Validate and return (start, end, selection, limit) from a request payload."""
        if not payload:
            raise ValueError('Missing JSON body')
        selection = payload.get('selection')
        if not selection or not isinstance(selection, dict):
            raise ValueError('Missing or invalid "selection"')
        for sensor, metrics in selection.items():
            if sensor not in SENSOR_DATA:
                raise ValueError(f'Unknown sensor: {sensor!r}')
            valid_metrics = set(SENSOR_DATA[sensor].data.keys())
            for metric in metrics:
                if metric not in valid_metrics:
                    raise ValueError(f'Unknown metric for {sensor}: {metric!r}')
        start = payload.get('start')
        end = payload.get('end')
        limit = payload.get('limit')
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError(f'"limit" must be a positive integer')
        return start, end, selection, limit

    def query_selection(conn, start, end, selection, limit):
        """Query the DB and return {sensor: {timestamps: [...], metric: [...]}}."""
        result = {}
        t_total = time.perf_counter()
        for sensor, metrics in selection.items():
            t0 = time.perf_counter()
            try:
                readings = db.get_readings(sensor, conn=conn, start=start,
                                           end=end, decimate=limit)
            except sqlite3.OperationalError:
                readings = {}  # missing sensor table
            app.logger.info('get_readings(%s): %.3fs, %d rows', sensor,
                            time.perf_counter() - t0,
                            len(readings.get('timestamp', [])))
            if not readings:
                result[sensor] = {'timestamps': []}
                result[sensor].update({m: [] for m in metrics})
                continue
            result[sensor] = {
                'timestamps': [to_unix_ms(ts) for ts in readings['timestamp']],
            }
            for metric in metrics:
                result[sensor][metric] = readings[metric]
        app.logger.info('query_selection total: %.3fs', time.perf_counter() - t_total)
        return result

    @app.get('/api/sensors')
    def api_sensors():
        """Return static sensor metadata from sensors.toml (no DB queries).

        The response only changes when sensors.toml changes; clients should
        cache it and only refetch after a page reload.
        """
        sensors = {
            sensor: {
                'name': sensor_data.name,
                'description': sensor_data.description,
                'metrics': {
                    metric: {'label': info.get('label', metric),
                             'unit': info.get('unit', '')}
                    for metric, info in sensor_data.data.items()
                },
            }
            for sensor, sensor_data in SENSOR_DATA.items()
        }
        return jsonify({'sensors': sensors})

    @app.get('/api/latest')
    def api_latest():
        """Return the latest reading for each sensor that has data.

        Accepts optional ?sensors=name1,name2 to limit which sensors are queried.
        Without a filter all configured sensors are queried (used for discovery).
        """
        conn = get_db()
        requested = request.args.get('sensors', '')
        sensors_to_query = (
            [s for s in requested.split(',') if s in SENSOR_DATA]
            if requested else list(SENSOR_DATA.keys())
        )
        threshold = timedelta(seconds=max(600, config.sensor_read_delay))
        now = datetime.now(timezone.utc)
        result = {}
        t_total = time.perf_counter()
        for sensor in sensors_to_query:
            sensor_data = SENSOR_DATA[sensor]
            metrics = list(sensor_data.data.keys())
            t0 = time.perf_counter()
            try:
                row = conn.execute(
                    f'SELECT sensor_id, timestamp, {", ".join(metrics)} '
                    f'FROM {sensor} ORDER BY id DESC LIMIT 1'
                ).fetchone()
            except sqlite3.OperationalError:
                continue  # missing sensor table
            app.logger.info('api_latest(%s): %.3fs', sensor, time.perf_counter() - t0)
            if row is None:
                continue
            sensor_id, timestamp, *values = row
            result[sensor] = {
                'sensor_id': sensor_id,
                'timestamp': timestamp,
                'active': now - parse_timestamp(timestamp) <= threshold,
                **dict(zip(metrics, values)),
            }
        app.logger.info('api_latest total: %.3fs, %d/%d sensors',
                        time.perf_counter() - t_total, len(result), len(sensors_to_query))
        return jsonify({'sensors': result})

    @app.post('/api/query')
    def api_query():
        """Return readings for the requested sensors/metrics/time range."""
        try:
            start, end, selection, limit = parse_selection(request.get_json())
        except ValueError as err:
            app.logger.warning('Bad request to /api/query: %s', err)
            return jsonify({'error': str(err)}), 400
        conn = get_db()
        result = query_selection(conn, start, end, selection, limit)
        count = sum(len(data['timestamps']) for data in result.values())
        return jsonify({'count': count, **result})

    @app.post('/api/export')
    def api_export():
        """Export readings as CSV or JSON (no decimation)."""
        payload = request.get_json()
        fmt = (payload or {}).get('format', 'csv')
        if fmt not in ('csv', 'json'):
            return jsonify({'error': f'Invalid format: {fmt!r}'}), 400
        try:
            start, end, selection, _ = parse_selection(payload)
        except ValueError as err:
            app.logger.warning('Bad request to /api/export: %s', err)
            return jsonify({'error': str(err)}), 400
        conn = get_db()
        result = query_selection(conn, start, end, selection, limit=None)
        if fmt == 'json':
            return Response(
                json.dumps(result),
                mimetype='application/json',
                headers={'Content-Disposition':
                         'attachment; filename=sensor_data.json'},
            )
        # CSV: one section per sensor is not spreadsheet-friendly, so we
        # use long format: sensor, timestamp, metric columns (union)
        all_metrics = sorted({m for metrics in selection.values()
                              for m in metrics})
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['sensor', 'timestamp', *all_metrics])
        for sensor, data in result.items():
            metrics = selection[sensor]
            for i, ts_ms in enumerate(data['timestamps']):
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                row = [sensor, ts.isoformat(timespec='seconds')]
                for metric in all_metrics:
                    row.append(data[metric][i] if metric in metrics else '')
                writer.writerow(row)
        return Response(
            buffer.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition':
                     'attachment; filename=sensor_data.csv'},
        )

    return app


def main():
    app = create_app()
    app.run(host=config.api_host, port=config.api_port)


if __name__ == '__main__':
    main()
