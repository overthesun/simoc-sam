echo | ifconfig | grep "192.168"
echo "Port 8081 Opening"
nc -4 -l 8081
# echo | netstat -ntlp | grep 8081
