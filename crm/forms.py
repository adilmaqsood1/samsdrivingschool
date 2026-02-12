from django import forms


class LeadForm(forms.Form):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50, required=False)
    subject = forms.CharField(max_length=200, required=False)
    message = forms.CharField(required=False, widget=forms.Textarea)


class StudentRegistrationForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class EnrollmentRequestForm(forms.Form):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50, required=False)
    package = forms.CharField(max_length=150, required=False)
    preferred_location = forms.CharField(max_length=120, required=False)
    preferred_schedule = forms.CharField(max_length=200, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea)


class LessonRequestForm(forms.Form):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50, required=False)
    preferred_date = forms.DateField(required=False)
    preferred_time = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea)
