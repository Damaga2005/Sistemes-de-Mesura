"""Harness compartido tests application: wiring real, DBs temporales."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.application.service import ApplicationService  # noqa: E402
from app.exam.grading import ExamGradingService  # noqa: E402
from app.exam.review import ExamReviewService  # noqa: E402
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")

_retriever = None


def retriever():
    global _retriever
    if _retriever is None:
        _retriever = RetrievalService(KB, INDEX)
    return _retriever


def build_app(tmp_path, reasoning_provider="extractive", _copy_gen=True,
              fresh_retriever=False):
    tmp_path = Path(tmp_path)
    qdb = str(tmp_path / "q.sqlite")
    if _copy_gen or not Path(qdb).exists():
        shutil.copyfile(GENDB, qdb)
    sdb = str(tmp_path / "s.sqlite")
    if reasoning_provider == "extractive":
        provider = ExtractiveProvider()
    elif reasoning_provider == "broken":
        provider = _BrokenProvider()
    else:
        raise ValueError(reasoning_provider)

    def _ret():
        if fresh_retriever:
            return RetrievalService(KB, INDEX)
        return retriever()
    reng = ReasoningEngine(_ret(), KB, provider=provider)
    eng = ExaminerEngine(_ret(), KB, qdb)
    QuestionStore(qdb)
    stu = StudentService(KB, qdb, sdb)
    loop = AdaptiveLoop(stu)
    exs = ExamSessionService(sdb, qdb, KB)
    exg = ExamGradingService(exs, stu)
    exr = ExamReviewService(exs, exg, stu, KB)
    app = ApplicationService(
        retriever=_ret(), reasoning=reng, examiner=eng,
        correction=stu.correction, students=stu, adaptive=loop,
        exam_sessions=exs, exam_grading=exg, exam_review=exr, kb_path=KB)
    return app


class _BrokenProvider:
    provider_name = "broken-test"
    model_name = "broken-0"

    def generate(self, *a, **k):
        raise RuntimeError("proveedor caído (inyectado)")


def ctx(app, student="alu-1", workflow="TUTOR", language="ca"):
    return app.create_context(student, workflow, language)


def reopen_app(tmp_path, reasoning_provider="extractive",
               fresh_retriever=False):
    """Reconstruye servicios sobre DBs existentes SIN copiar GENDB.

    Simula reinicio de proceso: solo sobreviven los ficheros.
    """
    return build_app(tmp_path, reasoning_provider=reasoning_provider,
                     _copy_gen=False, fresh_retriever=fresh_retriever)


def sess(app, student="alu-1", workflow="TUTOR", nonce="t"):
    return app.create_session(student, workflow, nonce=nonce)
