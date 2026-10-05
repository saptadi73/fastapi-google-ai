import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.core.config import ROOT
from app.schemas.help import HelpAnswer, HelpCitation
from app.services.openai_service import OpenAIService
from app.services.profiling_service import canonical_json

KNOWLEDGE_ROOT = ROOT / "docs" / "knowledge"
TOKEN_RE = re.compile(r"[a-zA-Z0-9À-ÿ_]+", re.UNICODE)
STOPWORDS = {
    "ada", "agar", "akan", "atau", "bagaimana", "bisa", "dan", "dari", "di", "ini",
    "itu", "ke", "pada", "saya", "sebagai", "untuk", "yang", "apa", "cara", "dengan",
}


@dataclass(frozen=True)
class KnowledgeArticle:
    article_id: str
    title: str
    summary: str
    routes: tuple[str, ...]
    audiences: tuple[str, ...]
    source: str
    body: str

    def public_record(self):
        return {
            "id": self.article_id,
            "title": self.title,
            "summary": self.summary,
            "routes": list(self.routes),
            "source": self.source,
        }


def _tokens(value: str):
    return [token.lower() for token in TOKEN_RE.findall(value) if token.lower() not in STOPWORDS]


def _route_matches(pattern: str, route: str | None):
    if not route:
        return False
    return route == pattern or (pattern.endswith("/*") and route.startswith(pattern[:-1]))


class KnowledgeBase:
    def __init__(self, root: Path = KNOWLEDGE_ROOT):
        self.root = root

    def articles(self, role: str):
        result = []
        for path in sorted(self.root.glob("*.md")):
            article = self._read(path)
            if "*" in article.audiences or role in article.audiences:
                result.append(article)
        return result

    @staticmethod
    def _read(path: Path):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---\n") or "\n---\n" not in raw[4:]:
            raise ValueError(f"Knowledge article tanpa front matter: {path.name}")
        header, body = raw[4:].split("\n---\n", 1)
        metadata = yaml.safe_load(header) or {}
        return KnowledgeArticle(
            article_id=str(metadata["id"]),
            title=str(metadata["title"]),
            summary=str(metadata["summary"]),
            routes=tuple(metadata.get("routes", [])),
            audiences=tuple(metadata.get("audiences", ["*"])),
            source=str(metadata.get("source", path.name)),
            body=body.strip(),
        )

    def search(self, question: str, role: str, route: str | None = None, limit: int = 5):
        query = _tokens(question)
        scored = []
        for article in self.articles(role):
            title_tokens = _tokens(article.title + " " + article.summary)
            body_tokens = _tokens(article.body)
            title_counts = {token: title_tokens.count(token) for token in set(title_tokens)}
            body_counts = {token: body_tokens.count(token) for token in set(body_tokens)}
            score = sum(5 * title_counts.get(token, 0) + math.log1p(body_counts.get(token, 0)) for token in query)
            if any(_route_matches(pattern, route) for pattern in article.routes):
                score += 4
            if score > 0:
                scored.append((score, article))
        return [article for _, article in sorted(scored, key=lambda item: (-item[0], item[1].article_id))[:limit]]


class HelpService:
    def __init__(self, user, knowledge: KnowledgeBase | None = None, ai=None):
        self.user = user
        self.knowledge = knowledge or KnowledgeBase()
        self.ai = ai or OpenAIService()

    def list_articles(self, route=None, query=None):
        articles = self.knowledge.articles(self.user.role)
        if query:
            articles = self.knowledge.search(query, self.user.role, route, limit=20)
        elif route:
            articles = [a for a in articles if any(_route_matches(p, route) for p in a.routes)]
        return [article.public_record() for article in articles]

    async def ask(self, request):
        articles = self.knowledge.search(request.question, self.user.role, request.route)
        if not articles:
            return HelpAnswer(
                answer=("Saya belum menemukan petunjuk yang sesuai dalam panduan aplikasi. "
                        "Coba sebutkan halaman, proses, atau status yang sedang Anda lihat."),
                insufficient_context=True,
                suggested_questions=["Bagaimana alur dari Google Sheet sampai dashboard?"],
            )
        context = canonical_json({
            "question": request.question,
            "current_route": request.route,
            "user_role": self.user.role,
            "knowledge_articles": [
                {
                    "id": article.article_id,
                    "title": article.title,
                    "summary": article.summary,
                    "content": article.body[:6000],
                }
                for article in articles
            ],
        })
        answer, meta = await self.ai.generate(self.user, "USER_HELP", context, HelpAnswer)
        allowed = {article.article_id: article for article in articles}
        citations = []
        seen = set()
        for citation in answer.citations:
            if citation.article_id in allowed and citation.article_id not in seen:
                article = allowed[citation.article_id]
                citations.append(HelpCitation(article_id=article.article_id, title=article.title))
                seen.add(article.article_id)
        if not citations and not answer.insufficient_context:
            article = articles[0]
            citations.append(HelpCitation(article_id=article.article_id, title=article.title))
        answer = answer.model_copy(update={"citations": citations})
        return answer, meta

