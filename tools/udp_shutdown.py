import subprocess
import socket
import time

buffsize = 1024
host = ''
port = 50001

locaddr = (host, port)
sock = socket.socket(socket.AF_INET, type=socket.SOCK_DGRAM)
sock.bind(locaddr)
while True:
    try :
        message, (ip, port) = sock.recvfrom(buffsize)
        message = message.decode(encoding='utf-8')
        time.sleep(1)
        print(message)
        if message == 'shutdown now':
            print('shutdown')
            subprocess.run(('/usr/sbin/shutdown' ,'now'))
    except KeyboardInterrupt:
        sock.close()
        break
    except:
        pass