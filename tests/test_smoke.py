import kaaran
import kaaran.synth


def test_package_imports():
    assert kaaran.__version__
    assert "SYNTHETIC" in kaaran.synth.SYNTHETIC_MARKER
