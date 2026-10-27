import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import Listing, Offer, Profile, Report


class SignupForm(UserCreationForm):
    nickname = forms.CharField(label='활동 이름', max_length=20)
    consent = forms.BooleanField(label='이용 안내와 개인정보 처리방침을 읽고 동의합니다.')
    class Meta:
        model = User
        fields = ['username', 'nickname', 'password1', 'password2']
    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if not re.fullmatch(r'[a-z0-9_]{3,30}', username):
            raise ValidationError('아이디는 영문 소문자, 숫자, 밑줄 3~30자로 입력해 주세요.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('이미 사용 중인 아이디입니다.')
        return username


class LoginForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data['username'].lower()


class ContactForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['nickname', 'contact_method', 'contact']
        widgets = {'contact': forms.TextInput(attrs={'placeholder': '오픈채팅 URL, 디스코드 ID 또는 이메일'})}
    def clean(self):
        data = super().clean()
        method, contact = data.get('contact_method'), data.get('contact', '').strip()
        if bool(method) != bool(contact):
            raise ValidationError('연락 방법과 연락처를 함께 입력하거나 모두 비워 주세요.')
        if method == 'kakao' and not re.fullmatch(r'https://open\.kakao\.com/o/[A-Za-z0-9]+/?', contact):
            self.add_error('contact', 'https://open.kakao.com/o/ 로 시작하는 오픈채팅 링크를 입력해 주세요.')
        if method == 'email':
            try:
                validate_email(contact)
            except ValidationError:
                self.add_error('contact', '올바른 연락용 이메일을 입력해 주세요.')
        data['contact'] = contact
        return data


class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ['server', 'job', 'title', 'level', 'goal', 'price', 'available', 'detail']
        widgets = {'detail': forms.Textarea(attrs={'rows': 5, 'placeholder': '작업 범위와 협의할 조건을 적어 주세요. 연락처와 게임 인증정보는 적지 마세요.'})}


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ['amount', 'unit', 'available', 'detail']
        widgets = {'detail': forms.Textarea(attrs={'rows': 4})}


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'detail']
        widgets = {'detail': forms.Textarea(attrs={'rows': 4})}


class ModerationForm(forms.Form):
    action = forms.ChoiceField(label='처리', choices=[('resolve', '처리 완료'), ('hide', '의뢰 숨김 및 처리 완료'), ('restore', '의뢰 공개 및 처리 완료'), ('dismiss', '신고 반려')])
    response = forms.CharField(label='처리 메모 (신고자에게 공개)', max_length=1000, widget=forms.Textarea(attrs={'rows': 3}))

# Bind offers/edits to the terms actually displayed to the user.
ListingForm.base_fields['edit_version'] = forms.IntegerField(required=False, widget=forms.HiddenInput)
OfferForm.base_fields['version'] = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
