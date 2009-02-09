from django.db import models
from datetime import datetime
from django.forms import ModelForm,HiddenInput,CharField,ValidationError,Widget
from django.conf import settings
import re

try:
    from recaptcha.client import captcha
except ImportError:
    if settings.CAPTCHA_HTTP or settings.CAPTCHA_SSL:
    	raise
    else:
        print "Recaptcha not installed.  Download from http://pypi.python.org/pypi/recaptcha-client."


class Whitelist(models.Model):
    """Model describes the whitelist.  Contains entries for ALL domains that have ever been requested
    Sites are not whitelisted until the enabled flag is set to true.  This allows us to track malware,
    banner ads etc. that are typically highly requested but never whitelisted."""

    PROTOCOL_CHOICES = (
        (1,'HTTP'),
        (2,'SSL'),
    )

    def get_protocol_choice(cls,this_string):
        """Return the database short version of the protocol string."""

        for (num,proto_string) in cls.PROTOCOL_CHOICES:
    	    if proto_string == this_string:
    		    return num
    	raise ValueError("No such protocol")

    get_protocol_choice = classmethod(get_protocol_choice)

    whitelist_id=models.AutoField("ID",primary_key=True)
    domain=models.CharField("Domain Name",max_length=70,blank=False)
    date_added=models.DateTimeField(db_index=True,auto_now_add=True,
                            help_text="""If the domain is whitelisted, this timestamp is the time it was added
                            to the whitelist.  If the domain is not whitelisted, it is the time the domain was 
                            first requested.""",blank=False)
    protocol=models.PositiveSmallIntegerField(db_index=True,choices=PROTOCOL_CHOICES,blank=False)
    username=models.CharField("Added By User",max_length=30,db_index=True,blank=False)
    client_ip=models.IPAddressField(db_index=True,blank=False)
    url=models.CharField(max_length=255,blank=True)
    comment=models.CharField(max_length=100,blank=True)
    enabled=models.BooleanField(db_index=True,default=False,help_text="If TRUE the domain is whitelisted",blank=False)
    hitcount=models.PositiveIntegerField(db_index=True,default=0,editable=False,blank=False)
    last_accessed=models.DateTimeField(default=datetime.now(),db_index=True,
                                    help_text="Time this domain was last requested",blank=False,editable=False)



    def save(self,force_insert=False, force_update=False):
        if not self.whitelist_id:
            self.date_added = datetime.now()
        super(Whitelist, self).save(force_insert) 

    class Meta:
        #This is more correct, but it causes problems with form submission
        #I want to be able to enable an existing entry, with this constraint
        #django invalidates my form submission because an entry already exists.
        #unique_together = (("domain", "protocol"),)
        unique_together = (("domain", "protocol","enabled"),)

    def __str__(self):
        return "%s: %s - %s %s %s hits" % (self.whitelist_id,self.get_protocol_display(),self.domain,self.username,self.hitcount)


class RecaptchaWidget(Widget):
    """ A Widget which "renders" the output of captcha.displayhtml """
    def render(self, *args, **kwargs):
        #FIXME: Should I just always use SSL here?
        return captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY)


class DummyWidget(Widget):
    """
    A dummy Widget class for a placeholder input field which will
    be created by captcha.displayhtml

    """
    # make sure that labels are not displayed either
    is_hidden=True
    def render(self, *args, **kwargs):
        return ''


class WhiteListForm(ModelForm):
    url=CharField(max_length=255,widget=HiddenInput,required=False)
    recaptcha_response_field = CharField(max_length=50,widget=RecaptchaWidget,required=True)
    recaptcha_challenge_field = CharField(widget=DummyWidget)

    def clean_domain(self):

        data = self.cleaned_data['domain']
        try:
            re.match("^([a-z0-9-]{1,50}\.){1,6}[a-z]{2,6}$",data).group()
            return data
        except AttributeError:
            raise ValidationError("Bad domain name.")

    def clean(self):

        #TODO:wrap in try
        try:
            check = captcha.submit(self.cleaned_data['recaptcha_challenge_field'],
                                    self.cleaned_data['recaptcha_response_field'],
                                    settings.RECAPTCHA_PRIVATE_KEY,
                                    settings.RECAPTCHA_IP_ADDR)
        except ValueError:
            raise ValidationError("Recaptcha error: fields missing")
#        except:
#            raise ValidationError("Error contacting recaptcha server")

        if not check.is_valid:
            raise ValidationError('You have not entered the correct words.  Use the mp3 link to listen to spoken words.')
        else:
            return self.cleaned_data

    class Meta:
        model = Whitelist 
        fields = ("domain", "protocol", "url", "comment")

