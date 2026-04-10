from __future__ import annotations

from datetime import date
from pathlib import Path

from src.gateway.gateway import LLMGateway
from src.gateway.session import Session
from src.registry import Registry
from src.writer.vault import VaultManager
from src.writer.weekly_writer import WeeklyWriter
from src.writer.frontmatter import parse_document


CONSOLIDATION_SYSTEM = """You are a market intelligence analyst specializing in Physical AI.
Your task is to consolidate raw collected data into a structured factual report.
Organize by company and by topic. Do NOT summarize — preserve all facts.
Include source reliability scores where available.
Use [[WikiLinks]] for company and topic names."""

CONSOLIDATION_PROMPT = """## Registry
Companies: {companies}
Keywords: {keywords}

## Raw Data (this week)
{raw_data}

## Instructions
Consolidate the above raw data into a structured report organized by:
1. Company-wise developments
2. Topic/trend-wise developments
Preserve all facts. Note source names and reliability scores."""


class Consolidator:
    def __init__(
        self,
        gateway: LLMGateway,
        model: str,
        vault: VaultManager,
        registry: Registry,
        weekly_writer: WeeklyWriter,
    ):
        self._gateway = gateway
        self._model = model
        self._vault = vault
        self._registry = registry
        self._weekly_writer = weekly_writer

    def run(self, week: str, date_range: str) -> tuple[Session, Path]:
        """Run consolidation. Returns (session for checkpoint, path to consolidated file)."""
        # 1. Read all raw data for this week's date range
        raw_data = self._read_raw_data(date_range)

        # 2. Create session and send consolidation request
        session = Session(gateway=self._gateway, model=self._model, system=CONSOLIDATION_SYSTEM)

        companies_str = ", ".join(f"{c.name}" for c in self._registry.companies)
        keywords_str = ", ".join(f"{k.name}" for k in self._registry.keywords)

        prompt = CONSOLIDATION_PROMPT.format(
            companies=companies_str,
            keywords=keywords_str,
            raw_data=raw_data,
        )

        response = session.send(prompt)

        # 3. Write consolidated report
        path = self._weekly_writer.write_consolidated(
            week=week,
            date_range=date_range,
            content=response.content,
        )

        return session, path

    def _read_raw_data(self, date_range: str) -> str:
        """Read raw files whose date folder falls within ``date_range``.

        로컬 패치 I5: 원본 플랜은 ``date_range``를 무시하고 ``raw/`` 전체를 스캔했습니다.
        이번 주 정제 호출이 과거 모든 raw 데이터를 다시 GPT5 Pro에 밀어넣어 비용 폭발과
        기간 오염이 발생했습니다. ``raw_writer``는 ``date`` 인자(``YYYY-MM-DD``)로 폴더를
        만들므로, 폴더 이름을 ``date.fromisoformat``로 파싱해 범위 내만 선택합니다.
        파싱 실패 폴더는 보수적으로 건너뜁니다.
        """
        raw_dir = self._vault.vault_path / "raw"
        if not raw_dir.exists():
            return "(No raw data found)"

        start, end = self._parse_date_range(date_range)

        all_content = []
        for date_dir in sorted(raw_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            try:
                dir_date = date.fromisoformat(date_dir.name)
            except ValueError:
                continue
            if start is not None and dir_date < start:
                continue
            if end is not None and dir_date > end:
                continue
            for md_file in sorted(date_dir.glob("*.md")):
                metadata, body = parse_document(md_file.read_text(encoding="utf-8"))
                source_info = metadata.get("source", {})
                source_name = source_info.get("name", "unknown") if isinstance(source_info, dict) else "unknown"
                all_content.append(
                    f"### {metadata.get('title', md_file.stem)}\n"
                    f"Source: {source_name} "
                    f"(reliability: {metadata.get('reliability', 'N/A')})\n"
                    f"{body}\n"
                )

        return "\n---\n".join(all_content) if all_content else "(No raw data found)"

    @staticmethod
    def _parse_date_range(date_range: str) -> tuple[date | None, date | None]:
        """Parse ``"YYYY-MM-DD ~ YYYY-MM-DD"`` into an inclusive (start, end) pair.

        포맷이 어긋나면 ``(None, None)``을 반환하여 필터링을 건너뜁니다 — 로컬
        실험 중 포맷 오타로 주간 정제가 빈 결과를 내는 것을 피하기 위한 안전장치.
        """
        if not date_range or "~" not in date_range:
            return None, None
        left, _, right = date_range.partition("~")
        try:
            start = date.fromisoformat(left.strip())
            end = date.fromisoformat(right.strip())
        except ValueError:
            return None, None
        return start, end
