# 라즈베리파이 Edge 장비 세팅 가이드

라즈베리파이 4B에 OS를 설치하고, 맥(노트북)에서 원격으로 `edge/` 코드를 받아 실행하기까지의 과정을 정리한다.

## 장비 구성

| 항목 | 사양 |
|---|---|
| 보드 | Raspberry Pi 4 Model B Rev 1.5, 4GB RAM |
| CPU | Cortex-A72 4코어, 최대 1.8GHz (aarch64) |
| 네트워크 | 기가비트 이더넷 `eth0`, Wi-Fi `wlan0` (802.11ac), Bluetooth 5.0 |
| OS | Raspberry Pi OS 64-bit (Debian 13 trixie), Python 3.13 |
| 저장장치 | microSD |
| 전원 | 5V 3A USB-C |

## 1. OS 설치 (Raspberry Pi Imager)

1. 맥에 Raspberry Pi Imager를 설치하고 SD카드를 연결한다. USB-C 포트밖에 없는 맥은 USB-C 리더기나 젠더가 필요하다.
2. 장치는 `Raspberry Pi 4`, 운영 체제는 `Raspberry Pi OS (64-bit)`, 저장소는 SD카드를 고른다.
3. **사용자 지정 항목을 빠짐없이 채운다.** 하나라도 건너뛰면 설정이 적용되지 않아, 모니터 없이(헤드리스) 접속할 수 없다.
   - 호스트 이름: 팀원끼리 겹치지 않게 정한다 (예: `cloudIOT2026`)
   - 로컬화: `Asia/Seoul`, 키보드 `us`
   - 사용자 이름과 비밀번호
   - Wi-Fi: SSID와 비밀번호, 국가 `KR`. 학교의 엔터프라이즈 Wi-Fi(eduroam 등)는 여기서 설정할 수 없으니 핫스팟을 쓴다.
   - 원격 접근: **SSH 활성화**
   - Raspberry Pi Connect: 선택 사항. 다른 네트워크에서 브라우저로 접속할 때 쓴다.
4. 굽기가 끝나면 SD카드의 `bootfs/user-data`에 사용자와 호스트명이 들어갔는지 확인할 수 있다. 내용이 전부 주석(`#`)이면 설정이 적용되지 않은 것이다.

## 2. 조립과 부팅

1. 방열판을 붙인다: 15×15는 SoC, 14×9는 RAM, 8×8은 USB 컨트롤러, 6×6은 PMIC.
2. 보드를 케이스에 넣고 SD카드를 **보드 뒷면 슬롯 끝까지** 꽂는다. 케이스와 보드 사이 틈에 끼우지 않도록 주의한다.
3. 전원은 마지막에 연결한다. 전원 스위치가 없어서 꽂으면 바로 켜진다.

| LED | 의미 |
|---|---|
| 빨간불 계속 켜짐 | 전원 정상 |
| 초록불 불규칙하게 깜빡임 | SD카드를 읽고 쓰는 중 (정상) |
| 초록불이 전혀 깜빡이지 않음 | SD카드 인식 실패. 다시 꽂는다 |

- 첫 부팅은 중간에 한 번 재부팅하며 3~5분 걸린다. 네트워크가 먼저 잡히고 SSH는 조금 뒤에 열린다.
- 끌 때는 `sudo shutdown -h now`를 실행하고 초록불이 꺼진 뒤 전원을 뺀다.

## 3. SSH 접속 (맥)

```bash
ping -c 3 <호스트명>.local
ssh <사용자>@<호스트명>.local
```

### 키 인증과 별칭 설정

키는 반드시 **맥 터미널**에서 만든다. 파이 안에서 `ssh-copy-id`를 실행하면 `No identities found` 오류가 난다.

```bash
ssh-keygen -t ed25519
ssh-copy-id <사용자>@<호스트명>.local
ssh-add --apple-use-keychain ~/.ssh/id_ed25519   # passphrase를 설정했다면 키체인에 저장
```

`~/.ssh/config`에 별칭을 추가해 두면 `ssh pi`로 바로 접속할 수 있다.

```
Host *
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519

Host pi
  HostName <호스트명>.local
  User <사용자>
```

### VS Code Remote-SSH

1. **Remote - SSH** 확장을 설치한다.
2. `Cmd+Shift+P`를 누르고 `Remote-SSH: Connect to Host...`에서 `pi`를 고른다. 플랫폼은 Linux를 선택한다.
3. 첫 연결에는 VS Code 서버를 설치하느라 1~3분 걸린다. 이때 초록 LED가 계속 깜빡인다.

## 4. 첫 부팅 후 기본 세팅

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

업데이트 도중에 재부팅했다면 다시 접속한 뒤 `sudo dpkg --configure -a`를 먼저 실행한다.

상태 확인:

```bash
cat /proc/device-tree/model; echo
lscpu | grep -E "Model name|^CPU\(s\)|max MHz"
free -h; df -h /; lsblk /dev/mmcblk0
hostname -I; ip -br link
vcgencmd measure_temp
```

## 5. 코드 배포 흐름

```
맥: 코드 수정 → edge 브랜치에 commit & push
파이: git pull → python -m edge.main 실행
```

파이는 코드를 받아서 실행만 한다. 수정과 커밋은 맥에서 한다.

### 최초 1회

```bash
sudo apt install -y git python3-venv python3-picamera2
git clone -b edge https://github.com/gidgogo/CloudAiot-.git ~/CloudAiot-
cd ~/CloudAiot-
python3 -m venv --system-site-packages .venv   # picamera2를 쓰려면 이 옵션이 필요
source .venv/bin/activate
pip install -r edge/requirements.txt
cp edge/config.example.yaml edge/config.yaml   # 커밋 금지
python -m edge.main --check-camera --source synthetic
```

### 매번

```bash
cd ~/CloudAiot- && source .venv/bin/activate
git pull
python -m edge.main --stream
```

- 기능 브랜치를 테스트하려면 `git fetch && git switch <브랜치>`로 바꾼다.
- `EDGE_TOKEN`과 서버 주소는 파이의 `edge/config.yaml`이나 환경변수에만 둔다.

## 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| Imager 저장소 목록이 비어 있음 | 맥이 SD카드를 인식하지 못한 상태. `diskutil list external`로 확인하고 리더기와 젠더를 점검한다. |
| 부팅 후 SSH 접속 불가, ping은 됨 | 첫 부팅이 아직 진행 중이다. 1~3분 더 기다린다. 계속 안 되면 SSH 활성화가 빠진 것이다. |
| `Permission denied (publickey,password)` | 키가 등록되지 않았거나 비밀번호가 틀렸다. |
| `Not a video capture device`, `cannot open camera 0` | 카메라가 연결되지 않았다. `--source synthetic`이나 `--file`로 테스트하거나 카메라를 연결한다. |
| 디스크 용량이 예상보다 작음 | `lsblk`로 카드 자체 크기를 확인한다. 파티션만 작으면 `sudo raspi-config --expand-rootfs`로 확장한다. |

## 다음 단계

- 버튼·LED·웹(MQTT)으로 송출 켜기/끄기, 부팅 시 자동 실행, 핫스팟 비상 등록: [edge-stream-control.md](edge-stream-control.md)
- 휴대폰에서 원격 셸로 Wi-Fi 바꾸기(Raspberry Pi Connect): 파이에서 `rpi-connect on && rpi-connect signin` 후 `loginctl enable-linger`로 로그인 없이 부팅 시 실행되게 한다. 이후 connect.raspberrypi.com → Remote shell.
