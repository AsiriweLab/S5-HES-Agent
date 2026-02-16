"""
Academic Paper Adapter for the Smart-HES Framework.

Ingests academic papers from multiple sources:
- Semantic Scholar API (primary, free)
- arXiv API (preprints)
- IEEE Xplore (user-provided PDFs)
- ACM Digital Library (metadata)
- Local PDF files

Provides unified interface for academic paper retrieval and indexing.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from loguru import logger


class AcademicSource(str, Enum):
    """Academic paper sources."""
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    IEEE = "ieee"
    ACM = "acm"
    USENIX = "usenix"
    SPRINGER = "springer"
    ELSEVIER = "elsevier"
    NATURE = "nature"
    CROSSREF = "crossref"
    OPENALEX = "openalex"
    CORE = "core"
    LOCAL_PDF = "local_pdf"


@dataclass
class Author:
    """Paper author."""
    name: str
    affiliation: Optional[str] = None
    author_id: Optional[str] = None


@dataclass
class AcademicPaper:
    """Represents an academic paper."""
    paper_id: str
    title: str
    abstract: str
    authors: list[Author] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None  # Conference/Journal name
    source: AcademicSource = AcademicSource.LOCAL_PDF
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    pdf_path: Optional[str] = None
    citations_count: int = 0
    keywords: list[str] = field(default_factory=list)
    full_text: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    indexed_at: datetime = field(default_factory=datetime.utcnow)

    def to_document(self) -> dict:
        """Convert to knowledge base document format."""
        author_str = ", ".join(a.name for a in self.authors[:5])
        if len(self.authors) > 5:
            author_str += " et al."

        content = f"Title: {self.title}\n\n"
        content += f"Authors: {author_str}\n"
        if self.year:
            content += f"Year: {self.year}\n"
        if self.venue:
            content += f"Venue: {self.venue}\n"
        content += f"\nAbstract:\n{self.abstract}"

        if self.full_text:
            content += f"\n\nFull Text:\n{self.full_text[:10000]}"

        return {
            "content": content,
            "metadata": {
                "title": self.title,
                "category": "academic",
                "source": self.source.value,
                "year": self.year,
                "authors": author_str,
                "venue": self.venue or "",
                "doi": self.doi or "",
                "arxiv_id": self.arxiv_id or "",
                "citations": self.citations_count,
                "keywords": ",".join(self.keywords),
                "paper_id": self.paper_id,
            },
        }

    def to_citation(self, style: str = "ieee") -> str:
        """Generate citation string."""
        author_str = ", ".join(a.name for a in self.authors[:3])
        if len(self.authors) > 3:
            author_str += " et al."

        if style == "ieee":
            citation = f'{author_str}, "{self.title}"'
            if self.venue:
                citation += f", in {self.venue}"
            if self.year:
                citation += f", {self.year}"
            if self.doi:
                citation += f", doi: {self.doi}"
            return citation
        elif style == "apa":
            citation = f"{author_str} ({self.year or 'n.d.'}). {self.title}."
            if self.venue:
                citation += f" {self.venue}."
            if self.doi:
                citation += f" https://doi.org/{self.doi}"
            return citation
        else:
            return f"{author_str}. {self.title}. {self.year or ''}"


class SemanticScholarClient:
    """Client for Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key

    async def search(
        self,
        query: str,
        limit: int = 10,
        year_range: tuple[int, int] = None,
        fields_of_study: list[str] = None,
    ) -> list[AcademicPaper]:
        """Search for papers."""
        params = {
            "query": query,
            "limit": limit,
            "fields": "paperId,title,abstract,authors,year,venue,citationCount,externalIds,url",
        }

        if year_range:
            params["year"] = f"{year_range[0]}-{year_range[1]}"

        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/paper/search",
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("data", []):
                    paper = self._parse_paper(item)
                    if paper:
                        papers.append(paper)

                logger.info(f"Semantic Scholar: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"Semantic Scholar search failed: {e}")
                return []

    async def get_paper(self, paper_id: str) -> Optional[AcademicPaper]:
        """Get a specific paper by ID."""
        fields = "paperId,title,abstract,authors,year,venue,citationCount,externalIds,url,tldr"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/paper/{paper_id}",
                    params={"fields": fields},
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_paper(data)

            except Exception as e:
                logger.error(f"Failed to get paper {paper_id}: {e}")
                return None

    def _parse_paper(self, data: dict) -> Optional[AcademicPaper]:
        """Parse Semantic Scholar response to AcademicPaper."""
        if not data.get("title") or not data.get("abstract"):
            return None

        authors = [
            Author(
                name=a.get("name", "Unknown"),
                author_id=a.get("authorId"),
            )
            for a in data.get("authors", [])
        ]

        external_ids = data.get("externalIds", {})

        return AcademicPaper(
            paper_id=data.get("paperId", ""),
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=authors,
            year=data.get("year"),
            venue=data.get("venue"),
            source=AcademicSource.SEMANTIC_SCHOLAR,
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            url=data.get("url"),
            citations_count=data.get("citationCount", 0),
        )


class ArxivClient:
    """Client for arXiv API."""

    BASE_URL = "https://export.arxiv.org/api/query"  # Use HTTPS

    async def search(
        self,
        query: str,
        limit: int = 10,
        categories: list[str] = None,
    ) -> list[AcademicPaper]:
        """Search arXiv papers."""
        # Build search query
        search_query = f"all:{query}"
        if categories:
            cat_query = " OR ".join(f"cat:{c}" for c in categories)
            search_query = f"({search_query}) AND ({cat_query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()

                papers = self._parse_response(response.text)
                logger.info(f"arXiv: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"arXiv search failed: {e}")
                return []

    def _parse_response(self, xml_content: str) -> list[AcademicPaper]:
        """Parse arXiv XML response."""
        import xml.etree.ElementTree as ET

        papers = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                paper = self._parse_entry(entry, ns)
                if paper:
                    papers.append(paper)

        except Exception as e:
            logger.error(f"Failed to parse arXiv response: {e}")

        return papers

    def _parse_entry(self, entry, ns: dict) -> Optional[AcademicPaper]:
        """Parse a single arXiv entry."""
        try:
            title = entry.find("atom:title", ns)
            abstract = entry.find("atom:summary", ns)
            arxiv_id_elem = entry.find("atom:id", ns)

            if title is None or abstract is None:
                return None

            # Extract arXiv ID from URL
            arxiv_url = arxiv_id_elem.text if arxiv_id_elem is not None else ""
            arxiv_id = arxiv_url.split("/")[-1] if arxiv_url else ""

            # Parse authors
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(Author(name=name.text))

            # Parse date
            published = entry.find("atom:published", ns)
            year = None
            if published is not None:
                try:
                    year = int(published.text[:4])
                except (ValueError, TypeError):
                    pass

            # Get PDF link
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                    break

            # Parse categories
            keywords = []
            for category in entry.findall("atom:category", ns):
                term = category.get("term")
                if term:
                    keywords.append(term)

            return AcademicPaper(
                paper_id=f"arxiv:{arxiv_id}",
                title=title.text.strip().replace("\n", " "),
                abstract=abstract.text.strip().replace("\n", " "),
                authors=authors,
                year=year,
                source=AcademicSource.ARXIV,
                arxiv_id=arxiv_id,
                url=pdf_url or arxiv_url,
                keywords=keywords,
            )

        except Exception as e:
            logger.error(f"Failed to parse arXiv entry: {e}")
            return None


class CrossRefClient:
    """
    Client for CrossRef API - aggregates metadata from major publishers.

    Covers: Springer, Elsevier, Nature, Wiley, Taylor & Francis, IEEE, ACM, etc.
    Free API, no key required (polite pool with email gets better rate limits).
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: Optional[str] = None):
        """
        Initialize CrossRef client.

        Args:
            email: Contact email for polite pool (better rate limits)
        """
        self.email = email
        self.headers = {"User-Agent": f"SmartHES-RAG/1.0 (mailto:{email})" if email else "SmartHES-RAG/1.0"}

    async def search(
        self,
        query: str,
        limit: int = 10,
        publisher: Optional[str] = None,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """
        Search CrossRef for papers.

        Args:
            query: Search query
            limit: Maximum results
            publisher: Filter by publisher name (e.g., "Springer", "Elsevier", "IEEE")
            from_year: Filter papers from this year onwards
        """
        params = {
            "query": query,
            "rows": limit,
            "select": "DOI,title,abstract,author,published-print,container-title,publisher,subject,URL",
        }

        # Note: CrossRef filter syntax is strict
        # publisher-name filter doesn't work well, use query.publisher-name instead
        if publisher:
            params["query.publisher-name"] = publisher

        if from_year:
            params["filter"] = f"from-pub-date:{from_year}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("message", {}).get("items", []):
                    paper = self._parse_item(item)
                    if paper:
                        papers.append(paper)

                logger.info(f"CrossRef: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"CrossRef search failed: {e}")
                return []

    def _parse_item(self, item: dict) -> Optional[AcademicPaper]:
        """Parse CrossRef item to AcademicPaper."""
        title_list = item.get("title", [])
        title = title_list[0] if title_list else None
        abstract = item.get("abstract", "")

        if not title:
            return None

        # Clean abstract (CrossRef abstracts may have JATS XML tags)
        if abstract:
            abstract = re.sub(r'<[^>]+>', '', abstract)

        # Parse authors
        authors = []
        for auth in item.get("author", []):
            name = f"{auth.get('given', '')} {auth.get('family', '')}".strip()
            if name:
                authors.append(Author(
                    name=name,
                    affiliation=auth.get("affiliation", [{}])[0].get("name") if auth.get("affiliation") else None,
                ))

        # Parse year
        year = None
        pub_date = item.get("published-print") or item.get("published-online")
        if pub_date and "date-parts" in pub_date:
            date_parts = pub_date["date-parts"][0]
            if date_parts:
                year = date_parts[0]

        # Determine source based on publisher
        publisher = item.get("publisher", "").lower()
        source = AcademicSource.CROSSREF
        if "springer" in publisher:
            source = AcademicSource.SPRINGER
        elif "elsevier" in publisher:
            source = AcademicSource.ELSEVIER
        elif "nature" in publisher:
            source = AcademicSource.NATURE
        elif "ieee" in publisher:
            source = AcademicSource.IEEE
        elif "acm" in publisher:
            source = AcademicSource.ACM

        doi = item.get("DOI", "")
        venue_list = item.get("container-title", [])

        return AcademicPaper(
            paper_id=f"crossref:{doi}" if doi else f"crossref:{hashlib.md5(title.encode()).hexdigest()[:12]}",
            title=title,
            abstract=abstract or f"Published in {venue_list[0] if venue_list else 'Unknown Journal'}",
            authors=authors,
            year=year,
            venue=venue_list[0] if venue_list else None,
            source=source,
            doi=doi,
            url=item.get("URL"),
            keywords=item.get("subject", [])[:10],
        )


class OpenAlexClient:
    """
    Client for OpenAlex API - comprehensive free academic database.

    OpenAlex is a free, open catalog of the global research system.
    Covers 250M+ works from all major publishers.
    No API key required (polite pool with email recommended).
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: Optional[str] = None):
        """
        Initialize OpenAlex client.

        Args:
            email: Contact email for polite pool (faster responses)
        """
        self.email = email

    async def search(
        self,
        query: str,
        limit: int = 10,
        from_year: Optional[int] = None,
        open_access_only: bool = False,
    ) -> list[AcademicPaper]:
        """
        Search OpenAlex for papers.

        Args:
            query: Search query
            limit: Maximum results
            from_year: Filter papers from this year onwards
            open_access_only: Only return open access papers
        """
        params = {
            "search": query,
            "per_page": limit,
            "select": "id,doi,title,abstract_inverted_index,authorships,publication_year,primary_location,open_access,cited_by_count,concepts",
        }

        if self.email:
            params["mailto"] = self.email

        # Add filters
        filters = []
        if from_year:
            filters.append(f"publication_year:>{from_year-1}")
        if open_access_only:
            filters.append("open_access.is_oa:true")
        if filters:
            params["filter"] = ",".join(filters)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/works",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("results", []):
                    paper = self._parse_work(item)
                    if paper:
                        papers.append(paper)

                logger.info(f"OpenAlex: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"OpenAlex search failed: {e}")
                return []

    def _parse_work(self, work: dict) -> Optional[AcademicPaper]:
        """Parse OpenAlex work to AcademicPaper."""
        title = work.get("title")
        if not title:
            return None

        # Reconstruct abstract from inverted index
        abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))

        # Parse authors
        authors = []
        for authorship in work.get("authorships", [])[:10]:
            author_info = authorship.get("author", {})
            name = author_info.get("display_name")
            if name:
                institutions = authorship.get("institutions", [])
                affiliation = institutions[0].get("display_name") if institutions else None
                authors.append(Author(name=name, affiliation=affiliation))

        # Get venue
        location = work.get("primary_location", {})
        source_info = location.get("source", {}) if location else {}
        venue = source_info.get("display_name") if source_info else None
        publisher = source_info.get("host_organization_name", "") if source_info else ""

        # Determine academic source
        source = AcademicSource.OPENALEX
        publisher_lower = publisher.lower() if publisher else ""
        if "springer" in publisher_lower:
            source = AcademicSource.SPRINGER
        elif "elsevier" in publisher_lower:
            source = AcademicSource.ELSEVIER
        elif "nature" in publisher_lower:
            source = AcademicSource.NATURE
        elif "ieee" in publisher_lower:
            source = AcademicSource.IEEE
        elif "acm" in publisher_lower:
            source = AcademicSource.ACM

        # Get DOI
        doi = work.get("doi", "")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        # Get keywords from concepts
        keywords = [c.get("display_name") for c in work.get("concepts", [])[:10] if c.get("display_name")]

        openalex_id = work.get("id", "").split("/")[-1]

        return AcademicPaper(
            paper_id=f"openalex:{openalex_id}",
            title=title,
            abstract=abstract or f"Published in {venue or 'Unknown Venue'}",
            authors=authors,
            year=work.get("publication_year"),
            venue=venue,
            source=source,
            doi=doi,
            url=work.get("doi") or work.get("id"),
            citations_count=work.get("cited_by_count", 0),
            keywords=keywords,
        )

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""

        # Build word position list
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))

        # Sort by position and join
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions)


class COREClient:
    """
    Client for CORE API - world's largest collection of open access research.

    CORE aggregates open access papers from repositories worldwide.
    Free API with optional API key for higher rate limits.
    """

    BASE_URL = "https://api.core.ac.uk/v3"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CORE client.

        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def search(
        self,
        query: str,
        limit: int = 10,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """
        Search CORE for open access papers.

        Args:
            query: Search query
            limit: Maximum results
            from_year: Filter papers from this year onwards
        """
        params = {
            "q": query,
            "limit": limit,
        }

        if from_year:
            params["q"] = f"{query} AND yearPublished:>={from_year}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/search/works/",  # Note trailing slash
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("results", []):
                    paper = self._parse_work(item)
                    if paper:
                        papers.append(paper)

                logger.info(f"CORE: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"CORE search failed: {e}")
                return []

    def _parse_work(self, work: dict) -> Optional[AcademicPaper]:
        """Parse CORE work to AcademicPaper."""
        title = work.get("title")
        abstract = work.get("abstract", "")

        if not title:
            return None

        # Parse authors
        authors = []
        for author_name in work.get("authors", [])[:10]:
            if isinstance(author_name, dict):
                name = author_name.get("name", "")
            else:
                name = str(author_name)
            if name:
                authors.append(Author(name=name))

        # Get year
        year = work.get("yearPublished")

        # Get DOI and URLs
        doi = work.get("doi", "")
        download_url = work.get("downloadUrl", "")

        core_id = work.get("id", "")

        return AcademicPaper(
            paper_id=f"core:{core_id}",
            title=title,
            abstract=abstract or "Abstract not available",
            authors=authors,
            year=year,
            venue=work.get("publisher"),
            source=AcademicSource.CORE,
            doi=doi,
            url=download_url or work.get("sourceFulltextUrls", [""])[0] if work.get("sourceFulltextUrls") else "",
            keywords=work.get("subjects", [])[:10] if work.get("subjects") else [],
        )


class IEEEXploreClient:
    """
    Client for IEEE Xplore API.

    IEEE Xplore provides free metadata access (abstracts, titles, authors).
    API key required - free registration at https://developer.ieee.org/
    Without API key, falls back to limited functionality.
    """

    BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize IEEE Xplore client.

        Args:
            api_key: IEEE API key (free registration required)
        """
        self.api_key = api_key

    async def search(
        self,
        query: str,
        limit: int = 10,
        from_year: Optional[int] = None,
        content_type: Optional[str] = None,
    ) -> list[AcademicPaper]:
        """
        Search IEEE Xplore for papers.

        Args:
            query: Search query
            limit: Maximum results
            from_year: Filter papers from this year onwards
            content_type: Filter by type (Journals, Conferences, Standards)
        """
        if not self.api_key:
            logger.warning("IEEE Xplore API key not configured - using CrossRef fallback for IEEE papers")
            # Fallback to CrossRef with IEEE filter
            crossref = CrossRefClient()
            return await crossref.search(query, limit, publisher="IEEE")

        params = {
            "apikey": self.api_key,
            "querytext": query,
            "max_records": limit,
            "format": "json",
        }

        if from_year:
            params["start_year"] = from_year

        if content_type:
            params["content_type"] = content_type

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                papers = []
                for item in data.get("articles", []):
                    paper = self._parse_article(item)
                    if paper:
                        papers.append(paper)

                logger.info(f"IEEE Xplore: Found {len(papers)} papers for '{query}'")
                return papers

            except Exception as e:
                logger.error(f"IEEE Xplore search failed: {e}")
                return []

    def _parse_article(self, article: dict) -> Optional[AcademicPaper]:
        """Parse IEEE Xplore article to AcademicPaper."""
        title = article.get("title")
        abstract = article.get("abstract", "")

        if not title:
            return None

        # Parse authors
        authors = []
        author_data = article.get("authors", {}).get("authors", [])
        for auth in author_data[:10]:
            name = auth.get("full_name", "")
            if name:
                authors.append(Author(
                    name=name,
                    affiliation=auth.get("affiliation", ""),
                ))

        # Get publication info
        year = article.get("publication_year")
        venue = article.get("publication_title", "")

        return AcademicPaper(
            paper_id=f"ieee:{article.get('article_number', '')}",
            title=title,
            abstract=abstract,
            authors=authors,
            year=int(year) if year else None,
            venue=venue,
            source=AcademicSource.IEEE,
            doi=article.get("doi", ""),
            url=article.get("pdf_url") or article.get("html_url", ""),
            citations_count=article.get("citing_paper_count", 0),
            keywords=article.get("index_terms", {}).get("ieee_terms", {}).get("terms", [])[:10],
        )


class LocalPDFIngester:
    """Ingests local PDF files."""

    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path("knowledge_base/academic_papers")

    async def ingest_pdf(
        self,
        pdf_path: Path,
        metadata: dict = None,
    ) -> Optional[AcademicPaper]:
        """Ingest a single PDF file."""
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return None

        metadata = metadata or {}

        try:
            # Try to extract text from PDF
            text = await self._extract_text(pdf_path)

            # Generate paper ID from filename
            paper_id = f"local:{hashlib.md5(str(pdf_path).encode()).hexdigest()[:12]}"

            # Extract title from metadata or filename
            title = metadata.get("title", pdf_path.stem.replace("_", " ").replace("-", " "))

            # Try to extract abstract from text
            abstract = self._extract_abstract(text) or text[:1000]

            # Parse authors from metadata
            authors = []
            if "authors" in metadata:
                for author_name in metadata["authors"]:
                    authors.append(Author(name=author_name))

            return AcademicPaper(
                paper_id=paper_id,
                title=title,
                abstract=abstract,
                authors=authors,
                year=metadata.get("year"),
                venue=metadata.get("venue"),
                source=AcademicSource.LOCAL_PDF,
                pdf_path=str(pdf_path),
                full_text=text,
                keywords=metadata.get("keywords", []),
            )

        except Exception as e:
            logger.error(f"Failed to ingest PDF {pdf_path}: {e}")
            return None

    async def _extract_text(self, pdf_path: Path) -> str:
        """Extract text from PDF."""
        try:
            # Try PyMuPDF first (if available)
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(str(pdf_path))
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text

            except ImportError:
                pass

            # Try pdfplumber (if available)
            try:
                import pdfplumber

                with pdfplumber.open(str(pdf_path)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                return text

            except ImportError:
                pass

            # Fallback: return empty (metadata only)
            logger.warning(f"No PDF library available, using metadata only for {pdf_path}")
            return ""

        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""

    def _extract_abstract(self, text: str) -> Optional[str]:
        """Extract abstract from paper text."""
        # Common abstract patterns
        patterns = [
            r"Abstract[:\s]*\n?(.*?)(?=\n\s*(?:Introduction|Keywords|1\.|I\.))",
            r"ABSTRACT[:\s]*\n?(.*?)(?=\n\s*(?:INTRODUCTION|KEYWORDS|1\.|I\.))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                abstract = match.group(1).strip()
                if len(abstract) > 100:
                    return abstract[:2000]

        return None

    async def ingest_directory(
        self,
        directory: Path = None,
        metadata_file: str = "metadata.json",
    ) -> list[AcademicPaper]:
        """Ingest all PDFs from a directory."""
        directory = directory or self.base_path
        papers = []

        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return papers

        # Load metadata if exists
        metadata_path = directory / metadata_file
        all_metadata = {}
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                all_metadata = json.load(f)

        # Process all PDFs
        for pdf_file in directory.glob("**/*.pdf"):
            file_key = pdf_file.stem
            metadata = all_metadata.get(file_key, {})

            paper = await self.ingest_pdf(pdf_file, metadata)
            if paper:
                papers.append(paper)

        logger.info(f"Ingested {len(papers)} papers from {directory}")
        return papers


class AcademicPaperAdapter:
    """
    Unified adapter for academic paper ingestion and retrieval.

    Supports multiple sources:
    - Semantic Scholar (API)
    - arXiv (API)
    - CrossRef (aggregates Springer, Elsevier, Nature, IEEE, ACM, Wiley, etc.)
    - OpenAlex (comprehensive free academic database, 250M+ works)
    - CORE (open access aggregator)
    - IEEE Xplore (with API key or CrossRef fallback)
    - Local PDFs
    """

    def __init__(
        self,
        semantic_scholar_key: Optional[str] = None,
        ieee_api_key: Optional[str] = None,
        core_api_key: Optional[str] = None,
        contact_email: Optional[str] = None,
        local_papers_path: Path = None,
    ):
        # Initialize all API clients
        self.semantic_scholar = SemanticScholarClient(api_key=semantic_scholar_key)
        self.arxiv = ArxivClient()
        self.crossref = CrossRefClient(email=contact_email)
        self.openalex = OpenAlexClient(email=contact_email)
        self.core = COREClient(api_key=core_api_key)
        self.ieee = IEEEXploreClient(api_key=ieee_api_key)
        self.local_ingester = LocalPDFIngester(base_path=local_papers_path)

        # Paper cache
        self._paper_cache: dict[str, AcademicPaper] = {}

        # Statistics
        self._stats = {
            "papers_indexed": 0,
            "semantic_scholar_queries": 0,
            "arxiv_queries": 0,
            "crossref_queries": 0,
            "openalex_queries": 0,
            "core_queries": 0,
            "ieee_queries": 0,
            "local_pdfs_ingested": 0,
        }

        logger.info("AcademicPaperAdapter initialized with extended publisher support")

    async def search(
        self,
        query: str,
        sources: list[AcademicSource] = None,
        limit_per_source: int = 5,
        year_range: tuple[int, int] = None,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """
        Search for academic papers across multiple sources.

        Args:
            query: Search query
            sources: Sources to search (default: arXiv and OpenAlex)
            limit_per_source: Results per source
            year_range: Optional year filter (start, end) for Semantic Scholar
            from_year: Filter papers from this year onwards

        Returns:
            List of papers from all sources
        """
        sources = sources or [AcademicSource.ARXIV, AcademicSource.OPENALEX]

        tasks = []

        if AcademicSource.SEMANTIC_SCHOLAR in sources:
            tasks.append(self._search_semantic_scholar(query, limit_per_source, year_range))

        if AcademicSource.ARXIV in sources:
            tasks.append(self._search_arxiv(query, limit_per_source))

        if AcademicSource.CROSSREF in sources:
            tasks.append(self._search_crossref(query, limit_per_source, from_year))

        if AcademicSource.OPENALEX in sources:
            tasks.append(self._search_openalex(query, limit_per_source, from_year))

        if AcademicSource.CORE in sources:
            tasks.append(self._search_core(query, limit_per_source, from_year))

        if AcademicSource.IEEE in sources:
            tasks.append(self._search_ieee(query, limit_per_source, from_year))

        # Search specific publishers via CrossRef
        if AcademicSource.SPRINGER in sources:
            tasks.append(self._search_crossref_publisher(query, "Springer", limit_per_source, from_year))

        if AcademicSource.ELSEVIER in sources:
            tasks.append(self._search_crossref_publisher(query, "Elsevier", limit_per_source, from_year))

        if AcademicSource.NATURE in sources:
            tasks.append(self._search_crossref_publisher(query, "Nature", limit_per_source, from_year))

        # Execute searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results and deduplicate by DOI
        all_papers = []
        seen_dois = set()
        seen_titles = set()

        for result in results:
            if isinstance(result, list):
                for paper in result:
                    # Deduplicate by DOI or title
                    if paper.doi and paper.doi in seen_dois:
                        continue
                    title_key = paper.title.lower().strip()[:100]
                    if title_key in seen_titles:
                        continue

                    if paper.doi:
                        seen_dois.add(paper.doi)
                    seen_titles.add(title_key)
                    all_papers.append(paper)
            elif isinstance(result, Exception):
                logger.error(f"Search task failed: {result}")

        # Cache papers
        for paper in all_papers:
            self._paper_cache[paper.paper_id] = paper

        return all_papers

    async def _search_semantic_scholar(
        self,
        query: str,
        limit: int,
        year_range: tuple[int, int] = None,
    ) -> list[AcademicPaper]:
        """Search Semantic Scholar."""
        self._stats["semantic_scholar_queries"] += 1
        return await self.semantic_scholar.search(
            query=query,
            limit=limit,
            year_range=year_range,
            fields_of_study=["Computer Science"],
        )

    async def _search_arxiv(self, query: str, limit: int) -> list[AcademicPaper]:
        """Search arXiv."""
        self._stats["arxiv_queries"] += 1
        return await self.arxiv.search(
            query=query,
            limit=limit,
            categories=["cs.CR", "cs.NI", "cs.DC"],  # Security, Networks, Distributed
        )

    async def _search_crossref(
        self,
        query: str,
        limit: int,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """Search CrossRef (all publishers)."""
        self._stats["crossref_queries"] += 1
        return await self.crossref.search(
            query=query,
            limit=limit,
            from_year=from_year,
        )

    async def _search_crossref_publisher(
        self,
        query: str,
        publisher: str,
        limit: int,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """Search CrossRef for a specific publisher."""
        self._stats["crossref_queries"] += 1
        return await self.crossref.search(
            query=query,
            limit=limit,
            publisher=publisher,
            from_year=from_year,
        )

    async def _search_openalex(
        self,
        query: str,
        limit: int,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """Search OpenAlex."""
        self._stats["openalex_queries"] += 1
        return await self.openalex.search(
            query=query,
            limit=limit,
            from_year=from_year,
        )

    async def _search_core(
        self,
        query: str,
        limit: int,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """Search CORE."""
        self._stats["core_queries"] += 1
        return await self.core.search(
            query=query,
            limit=limit,
            from_year=from_year,
        )

    async def _search_ieee(
        self,
        query: str,
        limit: int,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """Search IEEE Xplore."""
        self._stats["ieee_queries"] += 1
        return await self.ieee.search(
            query=query,
            limit=limit,
            from_year=from_year,
        )

    async def search_all_publishers(
        self,
        query: str,
        limit_per_source: int = 10,
        from_year: Optional[int] = None,
    ) -> list[AcademicPaper]:
        """
        Search all available publishers for comprehensive coverage.

        This is a convenience method that searches:
        - arXiv (preprints)
        - OpenAlex (comprehensive database)
        - CrossRef (major publishers)
        - CORE (open access)
        - Semantic Scholar (citations/metadata)

        Args:
            query: Search query
            limit_per_source: Results per source
            from_year: Filter papers from this year onwards

        Returns:
            Deduplicated list of papers from all sources
        """
        return await self.search(
            query=query,
            sources=[
                AcademicSource.ARXIV,
                AcademicSource.OPENALEX,
                AcademicSource.CROSSREF,
                AcademicSource.CORE,
                AcademicSource.SEMANTIC_SCHOLAR,
            ],
            limit_per_source=limit_per_source,
            from_year=from_year,
        )

    async def ingest_local_papers(
        self,
        directory: Path = None,
    ) -> list[AcademicPaper]:
        """Ingest papers from local directory."""
        papers = await self.local_ingester.ingest_directory(directory)
        self._stats["local_pdfs_ingested"] += len(papers)

        # Cache papers
        for paper in papers:
            self._paper_cache[paper.paper_id] = paper

        return papers

    async def ingest_ieee_paper(
        self,
        pdf_path: Path,
        title: str,
        authors: list[str],
        year: int,
        venue: str = "IEEE",
        doi: str = None,
        keywords: list[str] = None,
    ) -> Optional[AcademicPaper]:
        """
        Ingest a user-provided IEEE paper.

        Args:
            pdf_path: Path to PDF file
            title: Paper title
            authors: List of author names
            year: Publication year
            venue: Conference/journal name
            doi: DOI if available
            keywords: Paper keywords

        Returns:
            Ingested paper
        """
        metadata = {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "doi": doi,
            "keywords": keywords or [],
        }

        paper = await self.local_ingester.ingest_pdf(pdf_path, metadata)
        if paper:
            paper.source = AcademicSource.IEEE
            self._paper_cache[paper.paper_id] = paper
            self._stats["papers_indexed"] += 1

        return paper

    def get_paper(self, paper_id: str) -> Optional[AcademicPaper]:
        """Get a paper from cache."""
        return self._paper_cache.get(paper_id)

    def get_all_papers(self) -> list[AcademicPaper]:
        """Get all cached papers."""
        return list(self._paper_cache.values())

    def get_stats(self) -> dict:
        """Get adapter statistics."""
        return {
            **self._stats,
            "cached_papers": len(self._paper_cache),
        }

    def clear_cache(self) -> None:
        """Clear paper cache."""
        self._paper_cache.clear()


# Global instance
_academic_adapter: Optional[AcademicPaperAdapter] = None


def get_academic_adapter() -> AcademicPaperAdapter:
    """Get or create the global academic paper adapter."""
    global _academic_adapter
    if _academic_adapter is None:
        _academic_adapter = AcademicPaperAdapter()
    return _academic_adapter
