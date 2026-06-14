import socket
import struct
import threading
import os
import time
from datetime import datetime

# 获取脚本自身所在目录，确保日志写入共享文件夹
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "run_log.txt")
LOCK_FILE = os.path.join(BASE_DIR, "run_log.lock")
# 线程锁：保障多客户端并发写日志时不乱序
log_lock = threading.Lock()

def write_log(info):
    deadline = time.time() + 3  # 最多等待3秒，防锁残留
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() > deadline:
                try:
                    os.remove(LOCK_FILE)
                except FileNotFoundError:
                    pass
                deadline = time.time() + 3
            else:
                time.sleep(0.005)
    try:
        with log_lock:
            t = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{t}]server:{info}\n")
    finally:
        os.remove(LOCK_FILE)

def handle_client(conn, addr):
    # 持续处理当前客户端发来的报文，直到对方断开
    try:
        while True:
            # 先收2字节报文类型Type
            t_buf = conn.recv(2)
            if not t_buf:
                break  #空字节表示客户端正常关闭
            typ = struct.unpack(">H", t_buf)[0]
            write_log(f"收到{addr}报文Type={typ}")

            if typ == 1:
                # 初始化报文：Type=1 + 4字节总块数N
                n_buf = conn.recv(4)
                N = struct.unpack(">I", n_buf)[0]
                write_log(f"初始化报文，总块数N={N}")
                # 回复同意报文 Type=2
                pkg_agree = struct.pack(">H", 2)
                write_log(f"向{addr}发送agree报文type=2")
                conn.sendall(pkg_agree)
            elif typ == 3:
                # 数据请求报文：Type=3 + 4字节数据长度 + 数据
                l_buf = conn.recv(4)
                dat_len = struct.unpack(">I", l_buf)[0]
                raw = conn.recv(dat_len)
                s = raw.decode("ascii")
                rev_s = s[::-1]  # 字符串反转
                rev_bytes = rev_s.encode("ascii")
                # 回复报文 Type=4 + 4字节反转后长度 + 反转数据
                ans_head = struct.pack(">HI", 4, len(rev_bytes))
                ans_pkg = ans_head + rev_bytes
                write_log(f"收到请求数据:{s},返回反转:{rev_s}")
                conn.sendall(ans_pkg)
    except Exception as e:
        write_log(f"{addr}断开{e}")
    finally:
        conn.close()

def main():
    s = socket.socket()
    # SO_REUSEADDR：服务端重启后快速复用同一端口
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 9999))
    s.listen(10)
    # 写入空行分隔本次与上一次的运行日志
    deadline = time.time() + 3
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() > deadline:
                try:
                    os.remove(LOCK_FILE)
                except FileNotFoundError:
                    pass
                deadline = time.time() + 3
            else:
                time.sleep(0.005)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n")
    finally:
        os.remove(LOCK_FILE)
    print("TCP服务端启动，端口9999，支持多客户端")
    write_log("TCP服务端启动，端口9999，支持多客户端")
    while True:
        # 阻塞等待新客户端连接
        c, addr = s.accept()
        write_log(f"新客户端连接{addr}")
        # 每个客户端开独立线程处理，主线程继续accept
        th = threading.Thread(target=handle_client, args=(c, addr))
        th.daemon = True  # 主线程退出时子线程自动结束
        th.start()

if __name__ == "__main__":
    main()
