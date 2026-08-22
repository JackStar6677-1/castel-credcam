import cv2

import castel_credcam


def test_open_camera_accepts_network_url(monkeypatch) -> None:
    """Phone IP-camera URLs are forwarded unchanged to OpenCV."""
    calls = []
    sentinel = object()

    def fake_video_capture(source, backend):
        calls.append((source, backend))
        return sentinel

    monkeypatch.setattr(castel_credcam.cv2, "VideoCapture", fake_video_capture)

    result = castel_credcam.open_camera("http://192.168.1.50:8080/video")

    assert result is sentinel
    assert calls == [("http://192.168.1.50:8080/video", cv2.CAP_ANY)]
