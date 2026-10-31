"""Raspberry Pi entry point: capture -> metadata JSON -> JPEG binary."""
from __future__ import annotations
import argparse, asyncio
from pathlib import Path
from edge.config import load_config
from edge.frame_encoder import FrameEncoder
from edge.metrics import EdgeMetrics
from edge.websocket_client import FrameWebSocketClient

def check_camera(config_path: Path | None = None) -> None:
    from edge.camera import Camera
    config = load_config(config_path)["camera"]; camera = Camera(**config)
    try:
        camera.open(); frame = next(camera.frames(), None)
        if frame is None: raise RuntimeError("No camera frame received")
        print(f"Camera OK: {frame.shape[1]}x{frame.shape[0]}")
    finally: camera.close()

async def stream_frames(config_path: Path | None = None) -> None:
    config = load_config(config_path); camera_cfg, edge_cfg = config["camera"], config["edge"]
    camera, metrics = Camera(**camera_cfg), EdgeMetrics()
    encoder = FrameEncoder(camera_cfg["width"], camera_cfg["height"], camera_cfg["jpeg_quality"])
    client = FrameWebSocketClient(edge_cfg["server_url"], edge_cfg["edge_token"], edge_cfg["edge_id"])
    try:
        camera.open(); await client.connect()
        for frame in camera.frames():
            import time
            started = time.perf_counter()
            metadata, jpeg = encoder.encode(frame, edge_id=edge_cfg["edge_id"], camera_id=edge_cfg["camera_id"], mirrored=camera_cfg.get("mirrored", False), rotation_deg=camera_cfg.get("rotation_deg", 0))
            await client.send_frame(metadata, jpeg); metrics.mark_sent(started)
    finally:
        await client.close(); camera.close()

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path); parser.add_argument("--check-camera", action="store_true"); parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    if args.check_camera: check_camera(args.config)
    elif args.stream: asyncio.run(stream_frames(args.config))
    else: parser.print_help()
if __name__ == "__main__": main()
