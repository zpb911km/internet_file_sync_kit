import socket
import os
import sys
import tqdm
from base64 import b64encode, b64decode


socket.setdefaulttimeout(240)
if sys.platform.startswith("linux"):
    localFilePath = r"./"  # 保证此路径存在
elif sys.platform.startswith("win"):
    localFilePath = r'E:\ServerSyncFiles\\'  # 保证此路径存在
    # localFilePath = r"E:\myfiles\python\internet\Client\\"  # 保证此路径存在
ip_port = ('172.18.91.245', 60000)  # 写服务器的IP和端口
# ip_port = ('192.168.2.25', 60000)  # 写服务器的IP和端口
# ip_port = ("127.0.0.1", 60000)
PACK_LENGTH = 100 * 1024  # 定义数据包的大小为100kB


def get_files_with_timestamps():
    files_with_timestamps = ""

    # 遍历目录中的所有文件
    for root, _, files in os.walk(localFilePath):
        for file in files:
            file_path = os.path.join(root, file)
            # 获取文件的最后更改时间戳
            timestamp = os.path.getmtime(file_path)
            # 获取文件的大小
            file_size = os.path.getsize(file_path)
            # 将文件路径、时间戳和文件大小组合成一个字符串，中间用(>_<)分隔
            file_info = f"{file_path}(>_<){timestamp}(>_<){file_size}\n"
            files_with_timestamps += file_info.replace(localFilePath, "")

    return files_with_timestamps[:-1]  # 去掉最后一个换行符


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


def make_pack(files):
    send_pack = b""
    for file in files.split("\n"):
        if file == "":
            continue
        file = file.split("(>_<)")
        send_pack += (
            file[0] + "(>_<)" + str(file[1]) + "(>_<)" + str(file[2]) + "(>_<)"
        ).encode()
        with open(localFilePath + file[0], "rb") as f:
            # base64加密文件内容
            send_pack += b64encode(f.read())
            send_pack += "\n".encode()
        print(f"==> {file[0]}")
    return send_pack


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


def main():
    # 创建一个TCP/IP套接字
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 连接服务器
    print(f"连接到服务器 {ip_port}...")
    client_socket.connect(ip_port)
    print("Connected !!!")
    menu = """1) update
2) hard push
3) hard pull
: """
    try:
        method = int(input(menu))
    except ValueError:
        method = 1
    match method:
        case 1:
            server_flag = "update"
        case 2:
            server_flag = "hard push"
        case 3:
            server_flag = "hard pull"
        case _:
            server_flag = "update"

    send_data = f"{server_flag}(^_^){get_files_with_timestamps()}".encode()
    send_pack(client_socket, send_data)
    pack = recv_pack(client_socket)
    data = pack.decode()
    file_path_asked, file_recved = data.split(
        "这是一个分隔符，分隔请求列表和文件数据\n"
    )
    save_file(file_recved)
    pack = make_pack(file_path_asked)
    send_pack(client_socket, pack)
    print("文件发送完毕,按回车结束程序")
    client_socket.close()
    input()


if __name__ == "__main__":
    while True:
        try:
            main()
            break
        except Exception as e:
            print(f"Error: {e}")
