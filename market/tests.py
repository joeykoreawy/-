import secrets
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.core.management import call_command
from .models import AuditEvent, Listing, Offer, Profile, Report


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class MarketplaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = secrets.token_urlsafe(20)
        cls.owner = User.objects.create_user('owner', password=cls.password)
        cls.knight = User.objects.create_user('knight', password=cls.password)
        cls.other = User.objects.create_user('other', password=cls.password)
        cls.staff = User.objects.create_user('operator', password=cls.password, is_staff=True)
        for u in [cls.owner, cls.knight, cls.other, cls.staff]:
            Profile.objects.create(user=u, nickname=u.username, contact_method='discord', contact=f'private-{u.username}-contact')
    def setUp(self):
        self.a, self.b, self.c = Client(), Client(), Client()
        self.a.force_login(self.owner)
        self.b.force_login(self.knight)
        self.c.force_login(self.other)
        self.data = dict(server='태초', job='도사', title='태초 도사 의뢰', level='99레벨', goal='경험치 100억', price='억당 제안', available='평일 저녁', detail='공개 조건')
        self.listing = Listing.objects.create(owner=self.owner, **self.data)
    def make_offer(self, user=None, **kwargs):
        return Offer.objects.create(listing=self.listing, knight=user or self.knight, amount=500, unit='per100m', available='저녁 8시', detail='제안자만의 비공개 조건', listing_version=self.listing.version, **kwargs)
    def select(self, offer):
        return self.a.post(reverse('select', args=[self.listing.pk, offer.pk]))
    def test_public_reads_private_contacts_never_leak(self):
        offer = self.make_offer()
        for client in [Client(), self.a, self.b, self.c]:
            r = client.get(reverse('detail', args=[self.listing.pk]))
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'private-owner-contact')
            self.assertNotContains(r, 'private-knight-contact')
        self.assertNotContains(Client().get('/'), 'private-owner-contact')
        self.assertNotContains(self.c.get(reverse('detail', args=[self.listing.pk])), offer.detail)
    def test_two_account_full_lifecycle(self):
        self.assertTrue(self.b.login(username='knight', password=self.password))
        r = self.b.post(reverse('offer', args=[self.listing.pk]), dict(amount=600, unit='per100m', available='오늘 8시', detail='화면 공유 협의', version=1))
        self.assertEqual(r.status_code, 302)
        offer = Offer.objects.get(listing=self.listing)
        self.assertEqual(self.select(offer).status_code, 302)
        for client, contact in [(self.a, 'private-knight-contact'), (self.b, 'private-owner-contact')]:
            r = client.get(reverse('detail', args=[self.listing.pk]))
            self.assertContains(r, contact)
            self.assertEqual(r.headers['Cache-Control'], 'no-store, private')
        for client in [Client(), self.c]:
            r = client.get(reverse('detail', args=[self.listing.pk]))
            self.assertNotContains(r, 'private-owner-contact')
            self.assertNotContains(r, 'private-knight-contact')
        self.assertEqual(self.b.post(reverse('status', args=[self.listing.pk]), {'action': 'start'}).status_code, 302)
        self.assertEqual(self.a.post(reverse('status', args=[self.listing.pk]), {'action': 'complete'}).status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'completed')
    def test_create_shared_database_and_dual_roles(self):
        r = self.b.post(reverse('create'), self.data)
        self.assertEqual(r.status_code, 302)
        new = Listing.objects.get(owner=self.knight)
        self.assertContains(Client().get('/'), new.title)
        self.assertEqual(self.a.post(reverse('offer', args=[new.pk]), dict(amount=1000, unit='total', available='저녁', detail='역할 전환 없이 제안', version=1)).status_code, 302)
    def test_anonymous_cannot_write(self):
        paths = ['create', 'account', 'mine']
        for name in paths:
            self.assertEqual(Client().post(reverse(name), self.data).status_code, 302)
        for name in ['edit', 'delete', 'offer', 'status', 'report']:
            self.assertEqual(Client().post(reverse(name, args=[self.listing.pk]), self.data).status_code, 302)
        self.assertEqual(Listing.objects.count(), 1)
    def test_only_owner_can_edit_delete_select(self):
        offer = self.make_offer()
        for client in [self.b, self.c]:
            self.assertEqual(client.post(reverse('edit', args=[self.listing.pk]), self.data).status_code, 404)
            self.assertEqual(client.post(reverse('delete', args=[self.listing.pk])).status_code, 404)
            self.assertEqual(client.post(reverse('select', args=[self.listing.pk, offer.pk])).status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'open')
    def test_self_offer_forbidden(self):
        self.assertEqual(self.a.get(reverse('offer', args=[self.listing.pk])).status_code, 403)
    def test_disabled_servers_rejected(self):
        r = self.a.post(reverse('create'), dict(self.data, server='옛날바람'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Listing.objects.count(), 1)
    def test_tampered_owner_status_ignored(self):
        r = self.a.post(reverse('create'), dict(self.data, owner=self.other.pk, status='completed', is_hidden=True, selected_offer=100))
        self.assertEqual(r.status_code, 302)
        new = Listing.objects.latest('pk')
        self.assertEqual(new.owner, self.owner)
        self.assertEqual(new.status, 'open')
        self.assertFalse(new.is_hidden)
    def test_offer_amount_limits_and_unique_update(self):
        url = reverse('offer', args=[self.listing.pk])
        for amount in [0, -1, 1000000001]:
            self.assertEqual(self.b.post(url, dict(amount=amount, unit='total', available='저녁', detail='조건', version=1)).status_code, 200)
        self.assertFalse(Offer.objects.exists())
        for amount in [100, 200]:
            self.assertEqual(self.b.post(url, dict(amount=amount, unit='total', available='저녁', detail='조건', version=1)).status_code, 302)
        self.assertEqual(Offer.objects.count(), 1)
        self.assertEqual(Offer.objects.get().amount, 200)
    def test_stale_terms_require_offer_refresh(self):
        offer = self.make_offer()
        self.assertEqual(self.a.post(reverse('edit', args=[self.listing.pk]), dict(self.data, title='수정된 조건', edit_version=1)).status_code, 302)
        self.assertEqual(self.select(offer).status_code, 409)
        self.assertEqual(self.b.post(reverse('offer', args=[self.listing.pk]), dict(amount=400, unit='total', available='내일', detail='새 조건 확인', version=1)).status_code, 409)
        self.assertEqual(self.b.post(reverse('offer', args=[self.listing.pk]), dict(amount=400, unit='total', available='내일', detail='새 조건 확인', version=2)).status_code, 302)
        self.assertEqual(self.select(offer).status_code, 302)
    def test_stale_edit_rejected(self):
        self.assertEqual(self.a.post(reverse('edit', args=[self.listing.pk]), dict(self.data, edit_version=100)).status_code, 409)
    def test_no_reselection_or_cross_listing_offer(self):
        offer = self.make_offer()
        second = self.make_offer(user=self.other)
        another = Listing.objects.create(owner=self.owner, **self.data)
        self.assertEqual(self.a.post(reverse('select', args=[another.pk, offer.pk])).status_code, 404)
        self.assertEqual(self.select(offer).status_code, 302)
        self.assertEqual(self.select(second).status_code, 409)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.selected_offer_id, offer.pk)
        self.assertNotContains(self.c.get(reverse('detail', args=[self.listing.pk])), 'private-owner-contact')
    def test_state_permissions_and_cancel_revokes_contact(self):
        offer = self.make_offer()
        url = reverse('status', args=[self.listing.pk])
        self.assertEqual(self.a.post(url, {'action': 'complete'}).status_code, 409)
        self.select(offer)
        self.assertEqual(self.c.post(url, {'action': 'start'}).status_code, 403)
        self.assertEqual(self.a.post(url, {'action': 'start'}).status_code, 409)
        self.assertEqual(self.b.post(url, {'action': 'complete'}).status_code, 409)
        self.assertEqual(self.b.post(url, {'action': 'cancel'}).status_code, 302)
        self.assertNotContains(self.a.get(reverse('detail', args=[self.listing.pk])), 'private-knight-contact')
        self.assertNotContains(self.b.get(reverse('detail', args=[self.listing.pk])), 'private-owner-contact')
    def test_selected_offer_locked(self):
        offer = self.make_offer()
        self.select(offer)
        self.assertEqual(self.b.post(reverse('withdraw', args=[self.listing.pk, offer.pk])).status_code, 409)
        self.assertEqual(self.b.get(reverse('offer', args=[self.listing.pk])).status_code, 409)
        self.assertEqual(self.a.post(reverse('edit', args=[self.listing.pk]), self.data).status_code, 409)
        self.assertEqual(self.a.post(reverse('delete', args=[self.listing.pk])).status_code, 409)
    def test_own_offer_only_withdraw(self):
        offer = self.make_offer()
        self.assertEqual(self.c.post(reverse('withdraw', args=[self.listing.pk, offer.pk])).status_code, 404)
        self.assertEqual(self.b.post(reverse('withdraw', args=[self.listing.pk, offer.pk])).status_code, 302)
        self.assertFalse(Offer.objects.exists())
    def test_report_workflow_staff_only_hide_restore(self):
        offer = self.make_offer()
        self.select(offer)
        self.assertEqual(self.b.post(reverse('report', args=[self.listing.pk]), {'reason': 'fraud', 'detail': '사기 의심 신고'}).status_code, 302)
        item = Report.objects.get()
        for client in [Client(), self.a, self.b, self.c]:
            self.assertEqual(client.get(reverse('moderation')).status_code, 302)
            self.assertEqual(client.post(reverse('moderate', args=[item.pk]), {'action': 'hide', 'response': '부적절한 내용'}).status_code, 302)
        staff = Client(); staff.force_login(self.staff)
        self.assertEqual(staff.post(reverse('moderate', args=[item.pk]), {'action': 'hide', 'response': '확인 후 숨김'}).status_code, 302)
        self.assertEqual(Client().get(reverse('detail', args=[self.listing.pk])).status_code, 404)
        self.assertNotContains(self.a.get(reverse('detail', args=[self.listing.pk])), 'private-knight-contact')
        self.assertContains(self.b.get(reverse('mine')), '확인 후 숨김')
        self.assertNotContains(self.c.get(reverse('mine')), '사기 의심 신고')
        self.assertEqual(staff.post(reverse('moderate', args=[item.pk]), {'action': 'restore', 'response': '복원'}).status_code, 302)
        self.assertEqual(Client().get(reverse('detail', args=[self.listing.pk])).status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action='hide', actor=self.staff).exists())
    def test_report_survives_listing_deletion(self):
        self.b.post(reverse('report', args=[self.listing.pk]), {'reason': 'spam', 'detail': '도배 신고'})
        self.assertEqual(self.a.post(reverse('delete', args=[self.listing.pk])).status_code, 302)
        item = Report.objects.get()
        self.assertIsNone(item.listing)
        self.assertIn(self.data['title'], item.snapshot)
    def test_contact_update_and_erasure(self):
        offer = self.make_offer(); self.select(offer)
        self.assertEqual(self.b.post(reverse('account'), {'nickname': '기사', 'contact_method': '', 'contact': ''}).status_code, 302)
        self.assertNotContains(self.a.get(reverse('detail', args=[self.listing.pk])), 'private-knight-contact')
    def test_contact_formats(self):
        for method, value in [('kakao', 'javascript:alert(1)'), ('kakao', 'https://evil.example/o/hi'), ('email', 'invalid')]:
            self.assertEqual(self.a.post(reverse('account'), {'nickname': '회원', 'contact_method': method, 'contact': value}).status_code, 200)
    def test_xss_escaped_and_csp(self):
        self.listing.title = '<script>alert(1)</script>'
        self.listing.save()
        r = Client().get(reverse('detail', args=[self.listing.pk]))
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')
        self.assertIn("script-src 'self'", r.headers['Content-Security-Policy'])
    def test_csrf_and_get_mutations_rejected(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(reverse('create'), self.data).status_code, 403)
        self.assertEqual(strict.post(reverse('logout')).status_code, 403)
        offer = self.make_offer()
        for name, args in [('select', [self.listing.pk, offer.pk]), ('status', [self.listing.pk]), ('withdraw', [self.listing.pk, offer.pk])]:
            self.assertEqual(self.a.get(reverse(name, args=args)).status_code, 405)
        self.assertEqual(self.a.get(reverse('logout')).status_code, 405)
    def test_signup_password_hash_and_case_normalization(self):
        r = Client().post(reverse('signup'), {'username': 'New_Member', 'nickname': '새회원', 'password1': self.password, 'password2': self.password, 'consent': 'on'})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='new_member')
        self.assertNotEqual(u.password, self.password)
        self.assertTrue(u.check_password(self.password))
        self.assertEqual(u.profile.nickname, '새회원')
    def test_login_rate_limited(self):
        client = Client()
        for _ in range(12):
            self.assertEqual(client.post(reverse('login'), {'username': 'owner', 'password': 'wrong'}).status_code, 200)
        self.assertEqual(client.post(reverse('login'), {'username': 'owner', 'password': self.password}).status_code, 429)
    def test_anonymize_revokes_access(self):
        offer = self.make_offer(); self.select(offer)
        call_command('anonymize_user', 'knight', confirm=True, verbosity=0)
        self.knight.refresh_from_db(); self.listing.refresh_from_db()
        self.assertFalse(self.knight.is_active)
        self.assertEqual(self.knight.profile.contact, '')
        self.assertEqual(self.listing.status, 'cancelled')
    def test_contacts_required_for_matching(self):
        offer = self.make_offer()
        Profile.objects.filter(user=self.knight).update(contact='')
        self.assertEqual(self.select(offer).status_code, 409)
    def test_search_filters_and_health(self):
        self.assertContains(Client().get('/?job=도사'), self.data['title'])
        self.assertNotContains(Client().get('/?job=전사'), self.data['title'])
        self.assertNotContains(Client().get('/?q=없는검색어'), self.data['title'])
        self.assertEqual(Client().get('/health/').content, b'ok')

    def test_delete_cascades_offers_and_retains_audit(self):
        self.make_offer()
        self.assertEqual(self.a.post(reverse('delete', args=[self.listing.pk])).status_code, 302)
        self.assertFalse(Offer.objects.exists())
        event = AuditEvent.objects.get(action='delete')
        self.assertIsNone(event.listing)
        self.assertEqual(event.listing_id_snapshot, self.listing.pk)

    def test_administrator_login_is_also_throttled(self):
        client = Client()
        for _ in range(12):
            self.assertEqual(client.post('/admin/login/', {'username': 'operator', 'password': 'wrong', 'next': '/admin/'}).status_code, 200)
        self.assertEqual(client.post('/admin/login/', {'username': 'operator', 'password': self.password, 'next': '/admin/'}).status_code, 429)
