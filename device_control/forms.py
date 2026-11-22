from django import forms
from .protocol import PARAMETERS


class AIConfigForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, (_, low, high, label) in PARAMETERS.items():
            self.fields[name] = forms.FloatField(label=label, min_value=low, max_value=high,
                help_text=f'{low} – {high}', widget=forms.NumberInput(attrs={'step': '0.01'}))

    def parameters(self):
        return {key: self.cleaned_data[key] for key in PARAMETERS}
