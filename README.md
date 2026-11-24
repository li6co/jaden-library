# Jaden의 서재

3D 책장과 본문 읽기 기능이 있는 개인 서재 웹사이트입니다. 사이트 전체가 index.html 한 파일에 들어 있습니다.

## EPUB 자동 등록 (2단계)

### 최초 설치 (한 번만)

1. 기존 `main`을 백업하고, 이 패키지의 파일을 저장소 루트에 합칩니다. 기존 `index.html`은 교체하지 않습니다. 숨김 폴더 `.github`도 포함합니다. `feature/epub-registration` 같은 작업 브랜치에서 먼저 확인할 수 있습니다.
2. GitHub 저장소 Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 선택합니다. 기존 브랜치 방식에서 바꾸는 것은 자동 생성한 파일을 같은 워크플로에서 배포하기 위해 필요합니다. 기존 사이트 주소는 유지됩니다. 기존 설정을 기록해 두세요.
3. 변경을 `main`에 병합하거나 push한 뒤 Actions에서 `Build EPUB catalog and deploy Pages` 성공을 확인합니다. 실패하면 로그를 확인하고, 필요시 이전 커밋 및 Pages Source 설정으로 복구합니다.

### 책 추가 (3단계)

1. 공개 배포 권한이 확실한 DRM 없는 EPUB만 `books/`에 넣습니다. 구매한 개인용 파일은 절대로 저장소에 넣지 않습니다. public 저장소의 커밋 기록도 공개됩니다.
2. 필요하면 `books-overrides.json`을 수정한 뒤 `main`에 commit/push 합니다.
3. Actions 성공 후 `https://li6co.github.io/jaden-library/books.json`을 확인합니다. 3단계 전까지 기존 책장 화면에는 새 목록이 연결되지 않습니다.

수동 입력 예시 (`books-overrides.json`): 파일명 또는 생성된 `id`를 키로 사용합니다. 파일명 설정이 우선합니다.

```json
{
  "진달래꽃.epub": {
    "category": "시",
    "status": "reading",
    "note": "공개 가능한 한 줄 메모"
  }
}
```

상태: `unread`, `reading`, `finished`. 분류 기본값: `미분류`. 여기에 넣는 메모와 읽음 상태는 공개 정보이며, 추후 개인 기록은 별도 브라우저 저장으로 분리합니다.

## 로컬 검사

Python 3.12 (표준 라이브러리만 사용)에서 실행합니다.

```sh
python -m unittest discover -s tests -v
python scripts/build_books.py
```

두 번째 명령은 루트 `books.json`과 `covers/`를 갱신합니다. GitHub Actions는 동일 데이터를 `_site/`에 생성해 배포합니다. CI가 생성한 데이터는 저장소에 자동 커밋하지 않습니다. 저장소의 `books.json`은 초기 빈 목록이며, 사이트의 `books.json`은 매 빌드에서 새로 생성됩니다. 책 URL은 `books/…`처럼 상대 경로라 프로젝트 Pages 하위 경로를 지원합니다.

## 제한과 안전

- EPUB 2의 `meta name=cover`, EPUB 3의 `cover-image`, 표지 파일명 힌트를 지원합니다. PNG/JPEG/GIF/WebP 표지는 추출하며, 다른 형식(원본 SVG 포함) 또는 표지 없음은 안전하게 생성한 제목/저자 SVG로 대체합니다. 원본 SVG를 공개하지 않습니다(단, 공개 EPUB 원본 내부에는 포함되어 있을 수 있습니다).
- EPUB 파일 내용의 SHA-256을 ID로 사용합니다. 이름 변경에는 유지되지만 내용이 수정되면 ID가 달라집니다. 중복 원본은 실패 처리합니다. 추가일은 Git 최초 추가 커밋 날짜를 사용하고, 미커밋 파일은 수정 시각을 사용합니다.
- 알려진 DRM 표시/암호화 방식은 거부합니다. DRM 및 저작권을 완전히 판별하는 도구는 아닙니다. 파일을 push하기 전에 권리 확인이 반드시 필요합니다. EPUB은 최대 95 MiB, 표지는 최대 10 MiB입니다. 손상된 필수 구조나 중복 파일이 있으면 배포를 중단합니다.
- 테스트는 고전의 짧은 원문 발췌로 만든 최소 EPUB이며, 전체 전자책이나 브라우저 뷰어 테스트가 아닙니다. 테스트 파일은 배포하지 않습니다.
- 이 단계는 기존 `index.html`을 변경하지 않습니다. 책장 표시, lazy loading, 3D 모션, 페이지 이동, CFI 저장은 이후 단계에서 검증합니다. GitHub Actions는 현재 저장소 구조에 맞춰 `index.html`, `books/`, `covers/`, `books.json` 및 선택적 CNAME만 배포합니다. 이후 새 웹 자산 폴더가 생기면 복사 목록을 확장해야 합니다.
