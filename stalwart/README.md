# stalwart

Stalwart Mail Server for one mail domain: SMTP, submission and IMAP over
TLS, DKIM signing, the domain's DNS records, a first mailbox and an admin
from required parameters, designed in kadet-hub on Stalwart's image and
rendered by the kadet-hub `kubernetes` generator 1.16.0.

Source: `docker.io/stalwartlabs/stalwart:v1.0.3@sha256:73c684a84c24f5b4206ec266a8deb8986fe44a9f623997e07f084388d943c8bd`

Level: `deploys`

Requires: `cert-manager`

Stalwart Labs publishes no chart in a repository and no compose file. Its
Kubernetes guide prints a chart as text on a documentation page, which no
OCI or HTTP repository serves, so the recipe is designed on the image
Stalwart Labs builds (DEC-11 and DEC-261 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). Stalwart is AGPL-3.0 or
the proprietary Stalwart Enterprise License v2. The image contains the
Enterprise features, which stay off without a license key. The recipe
follows release line 1, and the digest is that of the index for linux/amd64,
linux/arm64, linux/arm/v6 and linux/arm/v7. The Job `stalwart-apply` runs
Stalwart's CLI image `docker.io/stalwartlabs/cli`, which has the same
licenses and covers linux/amd64 and linux/arm64.

Only the option `certificate` and the proof need cert-manager. A target
that provides the Secret `stalwart-tls` itself runs without it.

## Include

```yaml
classes:
  - recipes.stalwart
  # The DKIM key from a ref
  - recipes.stalwart.dkim
  # The certificate from cert-manager
  - recipes.stalwart.certificate
  # Outbound mail through a relay
  - recipes.stalwart.relay
  # The DNS records published into the included recipe powerdns
  - recipes.stalwart.powerdns
parameters:
  namespace: mail
  kapitan:
    vars:
      target: stalwart
  applications:
    stalwart:
      domain: example.com
      admin:
        password: <ref>
      mailbox:
        name: alice
        password: <ref>
      dkim:
        private_key: <ref>
      issuer:
        name: letsencrypt
        kind: ClusterIssuer
      relay:
        host: smtp.example.net
        username: example
        password: <ref>
    powerdns:
      zone: example.com
      api_key: <ref>
```

Stalwart reads its TLS certificate from the Secret `stalwart-tls` and its
DKIM key from the key `tls.key` of the Secret `stalwart-dkim`. The pod waits
until both exist. `recipes.stalwart.certificate` has cert-manager write
`stalwart-tls`, and `recipes.stalwart.dkim` renders `stalwart-dkim` from a
ref. Without an option, the target provides the Secret under that name.

`recipes.stalwart.powerdns` includes the recipe `powerdns`. Pin only this
recipe in the fetch inventory. The consumer workflow adds `powerdns` at the
digest this version's index record lists under `includes`. Kapitan's
`--fetch` reads no index, so for a local compile pull it by digest as the
recipe's page on kadet-hub.org shows.

## Required parameters

- `applications.stalwart.domain`, the mail domain, such as `example.com`.
- `applications.stalwart.admin.password`, as a ref. It is the password of
  the administrator `admin`, who has full access to Stalwart and its API.
- `applications.stalwart.mailbox.name` and
  `applications.stalwart.mailbox.password`, the local part and the password
  of the first mailbox, the password as a ref. Stalwart refuses weak
  passwords. The plan carries the password inside JSON, so it holds no
  double quote and no backslash. A ref such as `?{gpg:mail/alice||randomstr}`
  has neither.
- With `recipes.stalwart.dkim`: `applications.stalwart.dkim.private_key`, as
  a ref to an RSA private key in PEM, such as `?{gpg:mail/dkim||rsa:2048}`.
- With `recipes.stalwart.certificate`: `applications.stalwart.issuer`, the
  `name` and `kind` of the cert-manager issuer.
- With `recipes.stalwart.relay`: `applications.stalwart.relay.host`,
  `applications.stalwart.relay.username` and
  `applications.stalwart.relay.password`, the password as a ref without a
  double quote or a backslash.
- With `recipes.stalwart.powerdns`: `applications.powerdns.api_key`, the key
  of PowerDNS's HTTP API, which the included recipe `powerdns` requires, as
  a ref.

Without one of them the compile stops with `Interpolation key ... not
found` and that key.

## Settings

| Setting | Inventory |
|---|---|
| Stalwart version | `components.stalwart.image`, tag and digest |
| host name of the server, `mail.<domain>` | `applications.stalwart.hostname` |
| name of the administrator, `admin` | `applications.stalwart.admin.name` |
| DKIM selector, `stalwart` | `applications.stalwart.dkim.selector` |
| DMARC policy, `quarantine` | `applications.stalwart.dmarc.policy` |
| MTA-STS mode, `testing` | `applications.stalwart.mta_sts.mode` |
| MTA-STS policy id, `1` | `applications.stalwart.mta_sts.id` |
| port of the relay, 465 | `applications.stalwart.relay.port` |
| volume size, 10Gi | `components.stalwart.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.stalwart.resources` |
| Service type, `ClusterIP` | `components.stalwart.service.type` |

## Configuration

Stalwart 1.0 keeps its configuration in its database. The file
`config.json`, from the ConfigMap `stalwart-config`, names only the data
store, RocksDB on the claim `data`. The Job `stalwart-apply` writes the rest
through Stalwart's API with `stalwart-cli apply`, as Stalwart's guide for
declarative deployments does. Its plan, in the Secret `stalwart-apply`,
creates the domain, the certificate from `stalwart-tls`, the DKIM signature
from `stalwart-dkim` and the first mailbox with the alias `postmaster`. It
sets the host name and the MTA-STS mode, limits plain HTTP to the probes and
sends the log to the console. The Job retries until Stalwart answers.

Each line of the plan that names an object updates it when it exists instead
of adding a second one, so the plan can run again. The Job runs once. To
apply a changed plan, delete the Job and apply the target again. That sets
the first mailbox's password back to the parameter and keeps its app
passwords and API keys. Settings changed in the WebUI stay unless the plan
names them.

`admin` is Stalwart's recovery administrator, set through
`STALWART_RECOVERY_ADMIN` from the Secret `stalwart`. Stalwart accepts it in
every mode and the Job signs in with it. It has no mailbox.

The log reaches `kubectl logs` from the second start of the pod on, because
Stalwart reads its log settings only at start.

## TLS

Clients submit mail on port 465 and read it on port 993, both with implicit
TLS and the certificate of `stalwart-tls`. Port 587 and IMAP's port 143 do
not listen. Port 25 receives mail from other servers and offers no AUTH at
all, the default of Stalwart's `MtaStageAuth`. Port 443 serves the WebUI,
JMAP, the MTA-STS policy and autoconfiguration. The Service exposes these
four ports. The pod also listens on 995 (POP3 with TLS) and 4190
(ManageSieve, which refuses AUTH before STARTTLS), which the Service leaves
out. Port 8080 serves plain HTTP for the probes, and the plan answers every
other path on it from another address with 403.

Stalwart reads the certificate files only when it loads them. The sidecar
`reload-tls` compares `tls.crt` every 60 seconds and asks Stalwart to reload
the certificates when it changed, so a certificate that cert-manager renews
takes effect within a few minutes.

## DKIM and DNS records

Stalwart signs the mail its users send with `rsa-sha256` and relaxed
canonicalization, selector `stalwart`, with the key of `stalwart-dkim`.

The ConfigMap `stalwart-dns` holds the domain's records as a zone file: MX,
SPF (`v=spf1 mx -all`), DKIM, DMARC with `p=quarantine` and reports to
`postmaster`, MTA-STS (`_mta-sts` and a CNAME `mta-sts`), TLS-RPT
(`_smtp._tls`), SRV records for submission and IMAP, and the CNAMEs
`autoconfig` and `autodiscover`. The key of the DKIM record comes from the
private key at runtime. Kapitan's ref functions derive a public key only in
PEM, and DNS takes it as bare base64. At every start the init container
`dns` derives it with `openssl`, prints the complete zone and stops the pod
when the file holds no private key. `kubectl logs stalwart-0 -c dns` shows the
zone to copy into the domain's DNS. The init container runs only when the pod
starts, so after a change of the key or of a record, delete `stalwart-0`.

With `recipes.stalwart.powerdns`, the init container `powerdns` writes these
records into the zone `applications.powerdns.zone` of the included recipe
`powerdns`, through its API. Each name and type replaces what the zone held
there. The mail domain lies in that zone. A failure only prints a warning, so
mail starts without DNS.

The zone has no address record for the host name, because the address that
reaches the Service depends on the target. Add it where the zone lives. The
Service can carry the annotation `external-dns.kubernetes.io/hostname` for
the recipe `external-dns-powerdns` through
`components.stalwart.service.annotations`. That recipe writes only A records
for Services. The DNSEndpoint resources it could read for the other records
have no kadet-hub generator.

MTA-STS starts in mode `testing`, in which senders report TLS failures and
deliver anyway. Switch to `enforce` once the certificate is publicly valid,
and raise `mta_sts.id` with every change of the policy.

## Exposure

The Service is `ClusterIP`. Mail from the internet needs TCP ports 25, 465
and 993 on an address that keeps the client's IP. Stalwart checks SPF, its
rate limits and its bans by that IP. Behind a load balancer with
`externalTrafficPolicy: Cluster`, the Kubernetes default, the pod sees a
node's address. A ban then blocks every client behind that node, and SPF
fails for every sender.

- `components.stalwart.service.type: LoadBalancer` with
  `externalTrafficPolicy: Local` keeps the client IP. The `kubernetes`
  generator 1.16.0 renders no `externalTrafficPolicy`, so the field has to
  come from outside the recipe until a generator renders it.
- An L4 proxy in front of the cluster that speaks the PROXY protocol keeps it
  as well. Stalwart reads the PROXY header from the networks in
  `proxyTrustedNetworks` of its SystemSettings, which it reads only at start.
- `host_network: true` binds the ports on the node. Pod Security `baseline`
  and `restricted` refuse it.

kind has no load balancer and no external client, so none of this is
proven.

## Deliverability

A mail server on its own address has to earn the trust of the receiving
servers, and the recipe cannot do that part.

- Many residential and cloud networks block outbound connections to port
  25, so mail to other domains never leaves.
- Receivers check that the sending address has a reverse DNS (PTR) record
  that matches the host name. The PTR record is set by whoever owns the
  address, usually the provider.
- Addresses from residential ranges are listed in blocklists such as the
  Spamhaus PBL, and large providers reject or junk mail from them.

`recipes.stalwart.relay` sends mail for other domains through a relay
(smarthost) on port 465 with implicit TLS and the given credentials, which
avoids all three. Mail for the own domain stays local. The proof checks that
the route exists. It sends nothing to it, and delivery to other domains is
not proven.

## Encryption at rest

Proton Mail and Tuta are hosted services that cannot be self-hosted. The
closest that Stalwart offers is encryption at rest with each user's own key.
A user registers an OpenPGP key or an S/MIME certificate in the account
settings and turns on encryption at rest. From then on Stalwart stores every
message it delivers to that mailbox as a PGP/MIME or S/MIME message that only
the user's private key opens. Copies that a mail client stores, such as
sent mail, are encrypted only when the user also turns on
`encryptOnAppend`. The server-wide switch `atRestEnable` is on by
default, so the recipe sets nothing for it.

This protects stored mail against someone who later reads the disk, a
backup or the database, and against the server's administrators. It does
not protect the headers, which stay readable: From, To, Cc, Subject, Date
and the trace headers. It does not protect mail while Stalwart receives it,
nor mail in transit to other providers. That needs end-to-end OpenPGP or
S/MIME in the users' mail clients. Body search stops working for encrypted
messages, and webmail cannot read them.

## Proof

`check stalwart --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). The target includes
the options `certificate`, `relay` and `powerdns`, with a self-signed issuer.
Its DKIM key comes from a cert-manager Certificate in place of the option
`dkim`: a key in the repository fails the registry's secret scan, and a key
that a Kapitan ref function generates fails its read-only compile. All
addresses are in `example.test` (RFC 2606).

`tests/smoke` waits for `stalwart-apply` and starts a client pod. The
admin creates the second mailbox `b`. The first mailbox `a` sends to `b` on
465 with TLS and AUTH, and `b` reads the message on 993 with TLS, the
certificate verified both times. The smoke test resolves each record of the
zone through the Service `powerdns` and verifies the message's
DKIM-Signature against the key of the DKIM record in Python, not with
Stalwart. It reads the MTA-STS policy over HTTPS. It requires `550 5.7.1`
for a relay attempt without AUTH on port 25, `503` for AUTH there, and 403
for the API on port 8080. It reads the route of the option `relay` back
through the API. `b` registers an S/MIME certificate whose key the client pod
generates and never prints, and the next message for `b` is stored as an
S/MIME enveloped message without its text, which the key decrypts. A second
pod logs in, and its 101st failed login after that gets its address banned,
while the first pod still connects. A certificate that cert-manager issues
anew is served without a restart. After `stalwart-0` is deleted, `b` reads
the first message again.
