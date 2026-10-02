"""Unit (1 test): the straightening step, with a page the test draws itself.

One pytest item made of 3 named sub-checks. No dataset, model or network: the OpenCV straightener
runs on a tilted white page on a brown desk, and the graph wiring runs with fakes.
"""

from pathlib import Path

import cv2
import pytest
from PIL import Image, ImageDraw

from pipeline.core.config import Settings
from pipeline.core.errors import ConfigurationError
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation import FormScorer
from pipeline.flow.graph import build_graph
from pipeline.straightening import build_straightener
from pipeline.straightening.opencv import OpenCvStraightener

from ..checks import run_checks
from ..conftest import FakeOcrEngine, FakeStructurer, sample_truth

PAGE = (600, 850)
DESK = (118, 104, 92)


def _tilted_page(path: Path) -> None:
    """A white page with a black bar at the top-left, tilted 6 degrees on a brown desk."""
    page = Image.new("RGB", PAGE, "white")
    ImageDraw.Draw(page).rectangle((40, 30, 240, 60), fill="black")
    desk = Image.new("RGB", (800, 1050), DESK)
    desk.paste(page, (100, 100))
    desk.rotate(6, resample=Image.BICUBIC, fillcolor=DESK).save(path)


def _opencv_flattens_a_tilted_page(tmp_path: Path) -> None:
    """The page comes back upright, cropped to its own size, with its top-left bar in the top-left.

    A page found but not flattened would keep the desk border and the tilt, and a flip or rotation by
    90 degrees would move the bar, so the check covers the output size and the bar's position.
    """
    source, out = tmp_path / "tilted.png", tmp_path / "flat.jpg"
    _tilted_page(source)
    OpenCvStraightener().straighten(source, out)

    flat = cv2.imread(str(out), cv2.IMREAD_GRAYSCALE)
    height, width = flat.shape
    assert abs(width - PAGE[0]) < 0.05 * PAGE[0], (width, height)
    assert abs(height - PAGE[1]) < 0.05 * PAGE[1], (width, height)
    ys, xs = (flat < 80).nonzero()
    assert xs.mean() < width / 2 and ys.mean() < height / 10, (xs.mean(), ys.mean())


def _registry_builds_known_straighteners(tmp_path: Path) -> None:
    """No setting means no straightening, a known name builds it, an unknown name fails loudly.

    A wrong name must not fall back silently to "no straightening", because a run scored without the
    step would be reported as a run with it.
    """
    settings = Settings(groq_api_key="dummy-key-for-tests", langsmith_tracing=False)
    assert build_straightener(settings) is None
    opencv = settings.model_copy(update={"straightener": "opencv"})
    assert isinstance(build_straightener(opencv), OpenCvStraightener)
    with pytest.raises(ConfigurationError, match="opencv"):
        build_straightener(settings.model_copy(update={"straightener": "nope"}))


class _FakeStraightener:
    def __init__(self) -> None:
        self.calls = 0

    def straighten(self, image_path: Path, out_path: Path) -> None:
        self.calls += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"flat")


class _RecordingOcr(FakeOcrEngine):
    def read(self, image_path: Path):
        self.seen = image_path
        return super().read(image_path)


def _graph_reads_the_straightened_image(tmp_path: Path) -> None:
    """With a straightener, OCR reads the straightened file; with ``reuse`` the step is not run again.

    The OCR fake records the path it was given: it must be the saved ``straightened/<id>.jpg``, not
    the original photo. A second run with ``reuse=True`` must not call the straightener again.
    """
    store, ocr, straightener = (
        FileArtifactStore(tmp_path / "run"),
        _RecordingOcr(),
        _FakeStraightener(),
    )
    state = {"form_id": "000000", "image_path": "photo.jpg"}
    graph = build_graph(
        ocr,
        FakeStructurer(sample_truth(3)),
        FormScorer(),
        store,
        straightener=straightener,
    )
    graph.invoke(state)
    assert ocr.seen == store.path("straightened", "000000", ".jpg")
    assert ocr.seen.read_bytes() == b"flat"

    build_graph(
        ocr,
        FakeStructurer(sample_truth(3)),
        FormScorer(),
        store,
        reuse=True,
        straightener=straightener,
    ).invoke(state)
    assert straightener.calls == 1, "a saved straightened image was made again"


def test_straightening(tmp_path: Path) -> None:
    """The OpenCV straightener flattens a page, the registry picks it, the graph feeds OCR its output."""
    run_checks(
        [
            (
                "opencv_flattens_a_tilted_page",
                lambda: _opencv_flattens_a_tilted_page(tmp_path),
            ),
            (
                "registry_builds_known_straighteners",
                lambda: _registry_builds_known_straighteners(tmp_path),
            ),
            (
                "graph_reads_the_straightened_image",
                lambda: _graph_reads_the_straightened_image(tmp_path),
            ),
        ]
    )
