"""Two independent browser accounts against a running isolated test instance.
Run with a Python that has Playwright, after migrating a separate DJANGO_DATA_DIR.
Never point this at a public production site: it creates synthetic test accounts.
"""
import json
import os
import secrets
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = os.environ.get('E2E_BASE_URL', 'http://127.0.0.1:8001')
if base not in ['http://127.0.0.1:8001', 'http://localhost:8001']:
    raise SystemExit('Only an isolated local server on port 8001 is supported.')
out = Path('artifacts'); out.mkdir(exist_ok=True)
run = secrets.token_hex(4)
password = secrets.token_urlsafe(24)
results = []

def passed(label):
    results.append(label)
    print('PASS:', label, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    ctx_a = browser.new_context(viewport={'width': 1440, 'height': 1080})
    ctx_b = browser.new_context(viewport={'width': 1280, 'height': 960})
    ctx_guest = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
    a, b, guest = ctx_a.new_page(), ctx_b.new_page(), ctx_guest.new_page()
    errors = []
    for page in [a, b, guest]:
        page.on('pageerror', lambda e: errors.append(str(e)))
    guest.goto(base)
    assert guest.locator('.server[disabled]').count() == 3
    assert guest.locator('.server.active').inner_text().startswith('태')
    guest.screenshot(path=str(out/'mobile-empty.png'), full_page=True)
    passed('태초만 활성화, 나머지 서버 3개 준비 중')

    for page, role, nick in [(a, 'owner', '모험가'), (b, 'knight', '태초기사')]:
        page.goto(base + '/signup/')
        page.locator('[name=username]').fill(f'{role}_{run}')
        page.locator('[name=nickname]').fill(nick)
        page.locator('[name=password1]').fill(password)
        page.locator('[name=password2]').fill(password)
        page.locator('[name=consent]').check()
        page.get_by_role('button', name='회원가입', exact=True).click()
        expect(page).to_have_url(base+'/account/')
        page.locator('[name=contact_method]').select_option('discord')
        page.locator('[name=contact]').fill(f'{role}_private_{run}')
        page.get_by_role('button', name='내 정보 저장').click()
        expect(page.get_by_role('status')).to_contain_text('저장했습니다')
    passed('독립된 두 브라우저 세션에서 실제 회원가입·비공개 연락처 저장')

    a.goto(base + '/requests/new/')
    a.locator('[name=job]').select_option('도사')
    for name, value in {'title':'도사 200억 작지 기사님 구합니다', 'level':'99레벨 · 1차', 'goal':'경험치 200억', 'price':'억당 가격 제안', 'available':'평일 저녁 8시 이후', 'detail':'화면 공유 가능하신 기사님을 찾습니다. 작업 범위와 소요 시간을 함께 제안해 주세요.'}.items():
        a.locator(f'[name={name}]').fill(value)
    a.get_by_role('button', name='의뢰 등록하기', exact=True).click()
    expect(a.locator('h1')).to_have_text('도사 200억 작지 기사님 구합니다')
    detail_url = a.url
    b.goto(detail_url)
    guest.goto(detail_url)
    expect(guest.locator('h1')).to_have_text('도사 200억 작지 기사님 구합니다')
    for page in [a, b, guest]:
        assert f'owner_private_{run}' not in page.content()
        assert f'knight_private_{run}' not in page.content()
    passed('의뢰인 등록 → 별도 기사 계정과 비로그인 사용자에게 공용 DB 글 표시, 매칭 전 연락처 비공개')

    b.get_by_role('link', name='기사로 제안하기', exact=True).click()
    b.locator('[name=amount]').fill('450')
    b.locator('[name=unit]').select_option('per100m')
    b.locator('[name=available]').fill('오늘 저녁 8시부터')
    b.locator('[name=detail]').fill('화면 공유 가능합니다. 작업 범위와 정산은 시작 전에 협의하겠습니다.')
    b.get_by_role('button', name='제안 저장', exact=True).click()
    expect(b.locator('.offer-card')).to_contain_text('450원')
    a.reload()
    expect(a.locator('.offer-card')).to_contain_text('태초기사')
    expect(a.locator('.offer-card')).to_contain_text('450원')
    guest.reload()
    expect(guest.locator('.offer-card')).to_have_count(0)
    passed('기사 가격 제안 → 의뢰인 확인, 비로그인 사용자에게 제안 상세 비공개')
    a.screenshot(path=str(out/'offers-desktop.png'), full_page=True)

    a.locator('.offer-card input[type=checkbox]').check()
    a.get_by_role('button', name='이 기사 선택', exact=True).click()
    expect(a.locator('[data-testid=matched-contact]')).to_have_text(f'knight_private_{run}')
    b.reload()
    expect(b.locator('[data-testid=matched-contact]')).to_have_text(f'owner_private_{run}')
    guest.reload()
    expect(guest.locator('[data-testid=matched-contact]')).to_have_count(0)
    assert f'owner_private_{run}' not in guest.content()
    assert f'knight_private_{run}' not in guest.content()
    passed('의뢰인 기사 선택 → 매칭 확정, 두 당사자에게만 서로의 연락처 공개')
    a.screenshot(path=str(out/'matched-desktop.png'), full_page=True)
    # A visitor cannot mutate another person's listing even with its URL.
    r = ctx_guest.request.get(detail_url + 'edit/')
    assert r.status == 200 and '/login/' in r.url
    passed('비로그인 사용자의 의뢰 수정 진입은 로그인으로 전환')

    b.get_by_role('button', name='작업 시작', exact=True).click()
    expect(b.locator('.statusline .current')).to_have_text('03 진행 중')
    a.reload()
    a.get_by_role('button', name='작업 완료 확인', exact=True).click()
    expect(a.locator('.statusline .current')).to_have_text('04 완료')
    passed('선택된 기사 작업 시작 → 의뢰인 완료 확인')

    # Registering an own request and bidding both work without a role switch.
    b.goto(base + '/requests/new/')
    expect(b.locator('h1')).to_have_text('작지 의뢰 등록')
    passed('동일 회원의 기사·의뢰인 역할 모두 사용 가능')
    # Verify login independently after logout, not just signup auto-login.
    a.get_by_role('button', name='로그아웃', exact=True).click()
    a.goto(base + '/login/')
    a.locator('[name=username]').fill(f'owner_{run}')
    a.locator('[name=password]').fill(password)
    a.get_by_role('button', name='로그인', exact=True).click()
    expect(a.get_by_role('link', name='내 활동', exact=True).first).to_be_visible()
    passed('로그아웃 후 비밀번호로 재로그인')

    # Two requests from the same browser must never select a knight twice.
    a.goto(base + '/requests/new/')
    a.locator('[name=job]').select_option('전사')
    for name, value in {'title':'동시 선택 검증 의뢰', 'level':'99', 'goal':'100억', 'price':'제안', 'available':'저녁', 'detail':'합성 테스트용 의뢰'}.items():
        a.locator(f'[name={name}]').fill(value)
    a.get_by_role('button', name='의뢰 등록하기', exact=True).click()
    race_url = a.url
    b.goto(race_url + 'offer/')
    b.locator('[name=amount]').fill('1000')
    b.locator('[name=unit]').select_option('total')
    b.locator('[name=available]').fill('저녁')
    b.locator('[name=detail]').fill('동시 선택 검증')
    b.get_by_role('button', name='제안 저장', exact=True).click()
    a.goto(race_url)
    statuses = a.evaluate('''async () => {
        const form = document.querySelector('form[action$="/select/"]');
        const submit = () => fetch(form.action, {method: 'POST', body: new FormData(form)}).then(r => r.status);
        return await Promise.all([submit(), submit()]);
    }''')
    assert sorted(statuses) == [200, 409], statuses
    a.reload()
    expect(a.locator('.statusline .current')).to_have_text('02 매칭 완료')
    passed('실제 동시 기사 선택 요청: 한 번만 성공하고 중복 요청은 409로 거부')

    desktop = ctx_a.new_page()
    desktop.goto(base)
    desktop.screenshot(path=str(out/'home-desktop.png'), full_page=True)
    guest.goto(base)
    guest.screenshot(path=str(out/'home-mobile.png'), full_page=True)
    for page in [desktop, guest]:
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
    assert not errors, errors
    passed('데스크톱·모바일 가로 넘침 및 브라우저 스크립트 오류 없음')
    browser.close()
(out/'browser-results.json').write_text(json.dumps({'checks':results,'passed':len(results),'errors':errors}, ensure_ascii=False, indent=2))
print(f'{len(results)} browser checks passed. Screenshots and report: {out.resolve()}')
