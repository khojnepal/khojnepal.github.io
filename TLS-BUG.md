# udb.nepalpolice.gov.np — incomplete TLS certificate chain

**Impact during the 2026 flood response:** families and aid workers on clients that do
not fetch missing intermediates (most Android browsers, in-app browsers, curl, python
requests, and most API/scraper clients) cannot reach the missing-persons or
unidentified-bodies registers at all. Desktop Chrome and Safari usually mask the fault
by fetching the intermediate themselves, so the problem is easy to miss in testing.

## Diagnosis

    $ openssl s_client -connect udb.nepalpolice.gov.np:443 -servername udb.nepalpolice.gov.np
    depth=0 CN=*.nepalpolice.gov.np
    verify error:num=20:unable to get local issuer certificate
    verify error:num=21:unable to verify the first certificate
    Verify return code: 21 (unable to verify the first certificate)

    subject= C=NP, ST=Bagmati, L=Kathmandu, O=NEPAL POLICE HEADQUARTER, CN=*.nepalpolice.gov.np
    issuer=  C=BE, O=GlobalSign nv-sa, CN=GlobalSign RSA OV SSL CA 2018

The leaf certificate is valid and issued by a trusted CA. The server sends **only the
leaf** and omits the "GlobalSign RSA OV SSL CA 2018" intermediate, so clients cannot
build a path to the GlobalSign root.

## Confirmation

    $ curl https://udb.nepalpolice.gov.np/missing
    curl: (35) TLS connect error

    $ curl --cacert <(cat globalsign-ov-2018.pem /etc/ssl/certs/ca-certificates.crt) \
           https://udb.nepalpolice.gov.np/missing
    HTTP 200

Supplying the intermediate alone fixes it, which confirms the chain is the only fault.

## Fix

Serve the full chain — leaf followed by the GlobalSign RSA OV SSL CA 2018 intermediate —
in one file.

    # nginx
    ssl_certificate      /path/fullchain.pem;   # leaf + intermediate, in that order
    ssl_certificate_key  /path/privkey.pem;

    # apache
    SSLCertificateFile      /path/leaf.crt
    SSLCertificateChainFile /path/gsrsaovsslca2018.crt

Intermediate: http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt (DER — convert
with `openssl x509 -inform DER -in gsrsaovsslca2018.crt -out inter.pem`).

Verify with `openssl s_client -connect udb.nepalpolice.gov.np:443` — it should end in
`Verify return code: 0 (ok)` — or via https://www.ssllabs.com/ssltest/ ("Chain issues:
None").

## Secondary observation

Under load the host also drops TLS handshakes entirely (`curl: (35)`, connect times of
3-8s). Given the register is the primary public reference for ~9,400 missing-person
records, a cache/CDN in front of it would help families reach it.
