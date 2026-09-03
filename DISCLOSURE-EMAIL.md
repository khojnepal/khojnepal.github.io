# Draft disclosure email — NOT SENT

Review, edit, and send yourself. I have not contacted anyone.

**Suggested recipients** (all publicly listed):
- To:  cyberbureau@nepalpolice.gov.np — Nepal Police Cyber Bureau, +977 9851286770 / 01-5319044
- Cc:  cb_spokesperson@nepalpolice.gov.np — Information Officer
- Cc:  National Cyber Security Centre — https://ncsc.gov.np/ (contact form)

The Cyber Bureau is the reachable security contact inside Nepal Police; the
portal itself belongs to the Crime Investigation Department. Given the flood
response, the phone number is likely faster than email — the email is the
written record to follow up with.

---

**Subject:** Certificate chain fault blocking mobile access to udb.nepalpolice.gov.np (missing-persons register)

Dear Nepal Police Cyber Bureau,

I am writing about a server configuration fault on
https://udb.nepalpolice.gov.np that is currently preventing many people from
reaching the missing-persons and unidentified-bodies registers. Given that
these registers are a primary public reference during the current flood
response, I wanted to report it quickly. This is a configuration issue only —
no system was accessed or tested beyond ordinary public browsing of the site.

**The problem.** The server presents a valid GlobalSign certificate for
*.nepalpolice.gov.np, but does not send the intermediate certificate
("GlobalSign RSA OV SSL CA 2018") alongside it. Clients that do not fetch
missing intermediates on their own therefore cannot verify the connection and
fail to load the site at all. That includes most Android browsers, most in-app
browsers (links opened inside Facebook, Messenger, Viber, WhatsApp), and
command-line and API clients.

Desktop Chrome and Safari retrieve the intermediate themselves, so the site
appears to work correctly when tested on a desktop computer. This is likely
why the fault has not been noticed.

**How to reproduce.**

    openssl s_client -connect udb.nepalpolice.gov.np:443 -servername udb.nepalpolice.gov.np

returns:

    verify error:num=20:unable to get local issuer certificate
    Verify return code: 21 (unable to verify the first certificate)

Supplying the intermediate manually makes the same request succeed with HTTP
200, which confirms the chain is the only fault. The certificate itself is
valid and correctly issued.

**The fix.** Serve the full chain — the leaf certificate followed by the
GlobalSign RSA OV SSL CA 2018 intermediate — in a single file:

    # nginx
    ssl_certificate      /path/fullchain.pem;   # leaf + intermediate, in that order
    ssl_certificate_key  /path/privkey.pem;

    # apache
    SSLCertificateFile      /path/leaf.crt
    SSLCertificateChainFile /path/gsrsaovsslca2018.crt

The intermediate is available from GlobalSign at
http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt (DER format; convert
with `openssl x509 -inform DER -in gsrsaovsslca2018.crt -out inter.pem`).

After restarting the server, https://www.ssllabs.com/ssltest/ should report
"Chain issues: None".

**One further observation.** Under load the host also drops TLS handshakes
entirely, with connection times of three to eight seconds. Placing a cache or
CDN in front of the registers would help families reach them during the
current surge in traffic.

I am happy to provide any further detail that would help. Thank you for your
work during a very difficult period.

Kind regards,
[your name]
