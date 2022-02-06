from datetime import datetime

def format_reading(reading, *, time_fmt='%H:%M:%S'):
    """Format a sensor reading and return it as a string."""
    r = dict(reading)
    step_num = r.pop('step_num')
    dt = datetime.strptime(r.pop('timestamp'), '%Y-%m-%d %H:%M:%S.%f')
    timestamp = dt.strftime(time_fmt)
    result = []
    for key, value in r.items():
        v = f'{value:.2f}' if isinstance(value, float) else str(value)
        result.append(f'{key}: {v}')
    return f' {step_num:3}|{timestamp}  {"; ".join(result)}'
