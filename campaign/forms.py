from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User,ThematicArea, Activity, ImplementationStatus,Place

# User Creation Form for Regional Users
class RegionalUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password1', 'password2']

# User Creation Form for Place Users
class PlaceUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password1', 'password2']

# Authentication Forms
class NationalLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        if user.role != 'national':
            raise forms.ValidationError('Access denied.', code='invalid_login')

#regional_login form
class RegionalLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))

# Thematic Area Form
class ThematicAreaForm(forms.ModelForm):
    class Meta:
        model = ThematicArea
        fields = ['name', 'level', 'campaign']

# Activity Form
class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['name']

# Implementation Status Form
class ImplementationStatusForm(forms.ModelForm):
    class Meta:
        model = ImplementationStatus
        fields = ['scale', 'comments']
        widgets = {
            'scale': forms.Select(choices=[(0, '0'), (5, '5'), (10, '10')]),
            'comments': forms.Textarea(attrs={'rows': 2}),
        }

# Place Creation Form
class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = ['name']

#district login form
class PlaceLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))

class NationalUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password1', 'password2']


