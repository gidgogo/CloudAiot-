"""SSH로 Raspberry Pi 카메라 영상을 받아 로컬 화면에 실시간으로 띄운다.

Pi 쪽에는 별도 코드를 설치하지 않는다. SSH로 rpicam-vid(또는 ffmpeg)를 실행해
MJPEG 바이트 스트림을 stdout으로 내보내고, 로컬에서 JPEG 단위로 잘라 OpenCV로 표시한다.

사용 예:
    python scripts/ssh_stream_view.py                  # 카메라 자동 감지 (CSI → USB)
    python scripts/ssh_stream_view.py --source test    # 카메라 없이 테스트 패턴
    python scripts/ssh_stream_view.py --host pi --width 1280 --height 720 --fps 30

키: q 또는 ESC = 종료
필요: 로컬 `pip install opencv-python`, Pi에 rpicam-apps 또는 ffmpeg
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time

import cv2
import numpy as np

SOI = b"\xff\xd8"  # JPEG 시작
EOI = b"\xff\xd9"  # JPEG 끝


def remote_command(source: str, w: int, h: int, fps: int, device: str) -> str:
    # 정보 로그는 끄고 에러(예: 카메라 사용 중)는 로컬 터미널에 보이게 둔다
    # `exec VAR=값 cmd`는 bash에서 VAR=값을 명령으로 해석하므로 env로 넘긴다
    csi = (
        f"env LIBCAMERA_LOG_LEVELS='*:ERROR' rpicam-vid -v 0 -t 0 -n --codec mjpeg "
        f"--width {w} --height {h} --framerate {fps} -o -"
    )
    usb = (
        f"ffmpeg -loglevel error -f v4l2 -video_size {w}x{h} -framerate {fps} -i {device} "
        f"-c:v mjpeg -q:v 6 -f mjpeg -"
    )
    test = (
        f"ffmpeg -loglevel error -re -f lavfi -i testsrc=size={w}x{h}:rate={fps} "
        f"-c:v mjpeg -q:v 6 -f mjpeg -"
    )
    if source == "csi":
        return csi
    if source == "usb":
        return usb
    if source == "test":
        return test
    # auto: CSI 카메라가 있으면 CSI, 없으면 USB 장치, 둘 다 없으면 에러
    return (
        "if rpicam-hello --list-cameras 2>&1 | grep -qE '^[0-9]+ : '; then "
        f"echo '[pi] CSI camera' >&2; exec {csi}; "
        f"elif [ -e {device} ]; then echo '[pi] USB camera {device}' >&2; exec {usb}; "
        "else echo '[pi] 카메라를 찾지 못했습니다 (--source test 로 파이프라인만 확인 가능)' >&2; exit 1; fi"
    )


class LatestFrameReader(threading.Thread):
    """SSH stdout에서 JPEG를 잘라 가장 최근 프레임만 보관한다 (지연 누적 방지)."""

    def __init__(self, stream):
        super().__init__(daemon=True)
        self.stream = stream
        self.lock = threading.Lock()
        self.jpeg: bytes | None = None
        self.count = 0
        self.alive = True

    def run(self) -> None:
        buf = bytearray()
        while True:
            chunk = self.stream.read(65536)
            if not chunk:
                break
            buf += chunk
            last = None
            while True:
                start = buf.find(SOI)
                if start < 0:
                    buf.clear()
                    break
                end = buf.find(EOI, start + 2)
                if end < 0:
                    del buf[:start]
                    break
                last = bytes(buf[start : end + 2])
                del buf[: end + 2]
                self.count += 1
            if last is not None:
                with self.lock:
                    self.jpeg = last
        self.alive = False

    def take(self) -> bytes | None:
        with self.lock:
            jpeg, self.jpeg = self.jpeg, None
        return jpeg


def main() -> int:
    p = argparse.ArgumentParser(description="SSH 경유 Pi 카메라 실시간 뷰어")
    p.add_argument("--host", default="pi", help="ssh 호스트 (~/.ssh/config 별칭 가능)")
    p.add_argument("--source", choices=["auto", "csi", "usb", "test"], default="auto")
    p.add_argument("--device", default="/dev/video0", help="USB 카메라 장치")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    args = p.parse_args()

    cmd = remote_command(args.source, args.width, args.height, args.fps, args.device)
    ssh = subprocess.Popen(
        ["ssh", "-T", "-o", "ServerAliveInterval=5", args.host, cmd],
        stdout=subprocess.PIPE,
        bufsize=0,
    )
    reader = LatestFrameReader(ssh.stdout)
    reader.start()
    print(f"[local] {args.host} 에서 스트림 수신 중... (q/ESC 종료)", flush=True)

    win = f"Pi stream ({args.host})"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    fps, shown, t0 = 0.0, 0, time.monotonic()
    first_shown = False
    try:
        while reader.alive or reader.jpeg is not None:
            jpeg = reader.take()
            if jpeg is not None:
                frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    shown += 1
                    now = time.monotonic()
                    if now - t0 >= 1.0:
                        fps, shown, t0 = shown / (now - t0), 0, now
                    cv2.putText(frame, f"{fps:4.1f} fps", (10, 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.imshow(win, frame)
                    first_shown = True
            key = cv2.waitKey(5) & 0xFF
            if key in (ord("q"), 27):
                break
            # 첫 프레임 표시 전에는 macOS가 창을 '안 보임'으로 보고하므로 그 이후에만 검사
            if first_shown and cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        ssh.terminate()
        try:
            ssh.wait(timeout=2)
        except subprocess.TimeoutExpired:
            ssh.kill()
        cv2.destroyAllWindows()

    if reader.count == 0:
        print("[local] 수신된 프레임이 없습니다. 위의 [pi] 메시지를 확인하세요.", file=sys.stderr)
        return 1
    print(f"[local] 종료 (총 {reader.count} 프레임 수신)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
