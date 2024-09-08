import socket
import sys
import os
from base64 import b64encode, b64decode
import tqdm
import datetime


UPDATE_FLAG = 0
socket.setdefaulttimeout(240)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ip_port = ('172.18.91.245', 60000)  # 写服务器的IP和端口
# ip_port = ('192.168.2.25', 60000)  # 写服务器的IP和端口
# ip_port = ("127.0.0.1", 60000)
# localFilePath = r'/home/ZPB/prog/ServerSyncFiles/'  # 保证此路径存在
# localFilePath = r'E:\myfiles\python\internet\Server'
if sys.platform.startswith("linux"):
    localFilePath = r"/home/ZPB/prog/ServerSyncFiles/"  # 保证此路径存在
elif sys.platform.startswith("win"):
    localFilePath = r"E:\myfiles\python\internet\Server\\"  # 保证此路径存在
server_socket.bind(ip_port)
TIME_DIFF = 20  # 时间精度，单位秒
PACK_LENGTH = 100 * 1024  # 包的大小100kB，单位字节

# 监听连接
server_socket.listen(1)


def judge_file(flag, file_path_with_timestamp):
    server_files_with_timestamps = []

    # 遍历目录中的所有文件
    for root, _, files in os.walk(localFilePath):
        for file in files:
            file_path = os.path.join(root, file)
            # 获取文件的最后更改时间戳
            timestamp = os.path.getmtime(file_path)
            # 获取文件的大小
            file_size = os.path.getsize(file_path)
            file_info = [file_path.replace(localFilePath, ""), timestamp, file_size]
            server_files_with_timestamps.append(file_info)

    # 对比客户端和服务器端的文件列表，用时间戳比较文件是否有更新，把客户端新的文件存在列表中（和文件大小一起），把服务器端新的文件存在另一个列表中（和文件大小一起）
    client_files_with_timestamps = file_path_with_timestamp.split("\n")
    client_files_with_timestamps = list(map(lambda i: [i.split("(>_<)")[0], float(i.split("(>_<)")[1]), int(i.split("(>_<)")[2])], client_files_with_timestamps))

    if flag == "update":
        same_client_index = []
        same_server_index = []
        client_files = []
        server_files = []
        for client_index, client_file in enumerate(client_files_with_timestamps):
            for server_index, server_file in enumerate(server_files_with_timestamps):
                if client_file[0].replace("\\", "/").replace("//", "/") == server_file[0].replace("\\", "/").replace("//", "/"):
                    print(client_file[0])
                    if client_file[1] - server_file[1] > TIME_DIFF:
                        client_files.append(client_file)
                    elif client_file[1] - server_file[1] < -TIME_DIFF:
                        server_files.append(server_file)
                    else:
                        # server_files.append(server_file)
                        pass
                    same_client_index.append(client_index)
                    same_server_index.append(server_index)

        for client_index, client_file in enumerate(client_files_with_timestamps):
            if client_index not in same_client_index:
                client_files.append(client_file)

        for server_index, server_file in enumerate(server_files_with_timestamps):
            if server_index not in same_server_index:
                server_files.append(server_file)
        return client_files, server_files
    elif flag == "hard pull":
        return [], server_files_with_timestamps
    elif flag == "hard push":
        for file in server_files_with_timestamps:
            if file[0].replace("\\", "/").replace("//", "/") not in file_path_with_timestamp.replace("\\", "/").replace("//", "/"):
                os.remove((localFilePath + file[0]).replace("\\", "/").replace("//", "/"))
        return client_files_with_timestamps, []
    else:
        return [], []


def make_pack(client, server):
    send_pack = ""
    for file in client:
        send_pack += file[0] + "(>_<)" + str(file[1]) + "(>_<)" + str(file[2]) + "\n"
    send_pack += "这是一个分隔符，分隔请求列表和文件数据\n"
    send_pack = send_pack.encode()

    for file in server:
        send_pack += (file[0] + "(>_<)" + str(file[1]) + "(>_<)" + str(file[2]) + "(>_<)").encode()
        with open(localFilePath + file[0], "rb") as f:
            # base64加密文件内容
            send_pack += b64encode(f.read())
            send_pack += "\n".encode()
    return send_pack


def send_pack(client_socket, pack):
    while True:
        client_socket.send(str(len(pack)).encode())
        if client_socket.recv(1024).decode() == "Ready":
            break
    pack_list = [pack[i: i + PACK_LENGTH] for i in range(0, len(pack), PACK_LENGTH)]
    p = 0
    process_bar = tqdm.tqdm(total=len(pack_list))
    while p < len(pack_list):
        client_socket.send(str(len(pack_list[p])).encode())
        if client_socket.recv(1024).decode() != "Ready":
            continue
        client_socket.send(pack_list[p])
        try:
            client_socket.recv(1024).decode()
        except socket.timeout:
            client_socket.send("AGAIN".encode())
            continue
        p += 1
        process_bar.update(1)
    process_bar.close()


def recv_pack(client_socket):
    length = int(client_socket.recv(1024).decode())
    client_socket.send("Ready".encode())
    pack_num = sum([1 for _ in range(0, length, PACK_LENGTH)])
    recv_pack = b""
    p = 0
    process_bar = tqdm.tqdm(total=pack_num)
    while p < pack_num:
        length = int(client_socket.recv(1024).decode())
        client_socket.send("Ready".encode())
        data = b''
        full = False
        process_bar.update(1)
        while len(data) < length:
            got = client_socket.recv(length)
            if got == b'AGAIN':
                break
            data += got
            if len(data) == length:
                full = True
        if not full:
            process_bar.update(-1)
            continue
        client_socket.send("Success".encode())
        recv_pack += data
        p += 1
    process_bar.close()
    return recv_pack


def save_file(file_data):
    if file_data == "":
        return None
    file_path_list = file_data.split("\n")
    for file_path in file_path_list:
        if file_path == "":
            continue
        path = file_path.split("(>_<)")[0]
        name = path
        time = float(file_path.split("(>_<)")[1])
        content = file_path.split("(>_<)")[3]
        content = b64decode(content)
        path = (localFilePath + path).replace("\\", "/").replace("//", "/")
        print(path)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        open(path, "wb").write(content)
        os.utime(path, (time, time))
        print(f"<== {name}")
        if name == 'server.py':
            global UPDATE_FLAG
            UPDATE_FLAG = 1


def main():
    print("等待客户端连接...")
    client_socket, client_address = server_socket.accept()
    print(f"连接来自: {client_address}")
    pack = recv_pack(client_socket)
    flag = pack.decode().split("(^_^)")[0]
    file_path_with_timestamp = pack.decode().split("(^_^)")[1]
    client, server = judge_file(flag, file_path_with_timestamp)
    pack = make_pack(client, server)
    send_pack(client_socket, pack)
    pack = recv_pack(client_socket)
    save_file(pack.decode())
    print("数据接收完毕,关闭连接...")
    client_socket.close()


if __name__ == "__main__":
    while UPDATE_FLAG != 1:
        try:
            main()
        except Exception as e:
            # 输出现在的时刻
            print(f"[{datetime.datetime.now()}] 出现错误：{e}")
    print("更新完毕，结束服务...")
