# jitsi-meet

Jitsi Meet, video meetings in the browser, as its four services web, prosody,
jicofo and the video bridge jvb, rendered by the kadet-hub `kubernetes`
generator 1.14.0 from `docker-compose.yml` of docker-jitsi-meet stable-11248-3.

<!-- renovate: tag=stable-11248-3 -->
Source: `https://github.com/jitsi/docker-jitsi-meet/blob/fca3e3a578a1bdd527c20b9d86a31cfc362d5426/docker-compose.yml@sha256:e50de1a563bfeb005e7afd9b2defbeb298f21c8ea76ba0080724398191366a6e`

Level: `deploys`

The commit is the tag `stable-11248-3` of jitsi/docker-jitsi-meet, the
newest release on 2026-11-05. The project builds the four images
`ghcr.io/jitsi/web`, `prosody`, `jicofo` and `jvb` under the same tag, each
an index for linux/amd64 and linux/arm64. docker-jitsi-meet and the images
are Apache-2.0. The only Helm chart, jitsi-contrib/jitsi-helm, is published
by a community organization and not by the project, so the recipe is
derived from the compose file (DEC-10 and DEC-11 in
[docs/specs/recipes.md](../docs/specs/recipes.md)).

web serves the Jitsi Meet web app with nginx and proxies BOSH and the XMPP
WebSocket to prosody, the XMPP server that carries the signalling. jicofo
manages each meeting and allocates it on jvb, which forwards the audio and
video of the participants. The images run as the user `s6`, UID 1000, on a
read-only root filesystem, so the target's namespace may enforce the Pod
Security level `baseline`. On start jvb asks a public STUN server of
jitsi.net for the address it reaches the internet from, as with the compose
file.

## Include

```yaml
classes:
  - recipes.jitsi-meet
parameters:
  namespace: jitsi-meet
  kapitan:
    vars:
      target: jitsi-meet
  applications:
    jitsi-meet:
      jicofo_auth_password: <ref>
      jvb_auth_password: <ref>
      moderator_password: <ref>
```

## Required parameters

`applications.jitsi-meet.jicofo_auth_password` is `JICOFO_AUTH_PASSWORD`,
with which jicofo logs in to prosody as `focus@auth.meet.jitsi`.
`applications.jitsi-meet.jvb_auth_password` is `JVB_AUTH_PASSWORD`, with
which jvb logs in as `jvb@auth.meet.jitsi`. The compose setup has
`gen-passwords.sh` write random values, such as `openssl rand -hex 16`
prints, and any such string works. `applications.jitsi-meet.moderator_password`
is the password of `moderator@meet.jitsi`, the first user who may open a
meeting. Set all three as refs with the backend of your choice. Without one
of them the compile stops with `Interpolation key '<key>' not found`.

## Meetings, guests and the moderator

The compose file's defaults let anyone who reaches web open a meeting. The
recipe sets Jitsi's secure domain with guests instead (DEC-310): a user of
the domain `meet.jitsi` logs in to open a meeting, and guests join a meeting
that is open without an account, on the domain `guest.meet.jitsi`. prosody
offers no in-band registration, so users exist only where an operator
creates them.

Once prosody answers, a postStart hook of its container creates
`moderator@meet.jitsi` with `applications.jitsi-meet.moderator_password`,
or sets that password when the account exists (DEC-311). A changed
parameter therefore takes effect when prosody's pod restarts. Further
users are created in prosody's pod:

```sh
kubectl exec jitsi-meet-prosody-0 -- prosodyctl --config /run/prosody/config/prosody.cfg.lua \
  shell user create <name>@meet.jitsi <password>
```

## Media and exposure

jvb sends and receives media on UDP port 10000 at the addresses it
advertises to the clients: its pod IP and the address that STUN reports.
The Service `jitsi-meet-jvb` has the port 10000/UDP as a `ClusterIP`. A
client outside the cluster reaches jvb only when the target exposes that
port, such as with a `LoadBalancer` Service that carries UDP, and sets
`JVB_ADVERTISE_IPS` to the address the clients reach, with `#<port>` after
it when that port is not 10000. Clients behind a firewall that drops UDP
also need a TURN server, which docker-jitsi-meet does not run and prosody
announces through `TURN_HOST` and its related variables. The recipe exposes
nothing and sets neither (DEC-312).

jicofo grants a meeting also before jvb has joined it, and then offers its
participants no session, on kind not even within a minute after jvb joined.
A meeting opened in the first seconds after jvb starts or restarts
therefore has no audio and video. No probe holds jicofo back until it
knows a bridge. The compose file and the images define no healthcheck, and
jicofo's `/about/health` answers 404 unless `JICOFO_ENABLE_HEALTH_CHECKS`
is set. Whether it then fails without a bridge is not tested.

Browsers allow camera and microphone only on an HTTPS page. web serves
HTTPS on 8443 with a self-signed certificate it keeps on its claim. A
target puts a Gateway or Ingress with a real certificate in front of port
8000 or 8443 and sets `PUBLIC_URL` to its address.

## Settings

`<c>` stands for each of the components `jitsi-meet`, `jitsi-meet-prosody`,
`jitsi-meet-jicofo` and `jitsi-meet-jvb`.

| Setting | Inventory |
|---|---|
| Jitsi release, stable-11248-3 | `components.<c>.image`, tag and digest, the same release for all four |
| time zone, `UTC` from `env.example` | `components.<c>.env.TZ` |
| public URL, unset | `components.jitsi-meet.env.PUBLIC_URL` |
| media address, unset | `components.jitsi-meet-jvb.env.JVB_ADVERTISE_IPS` |
| user name of the first moderator, `moderator` | `components.jitsi-meet-prosody.env.MODERATOR_USER` |
| cluster domain, `cluster.local` | `applications.jitsi-meet.cluster_domain` |
| other variables of `env.example`, such as `ENABLE_LOBBY` | `components.<c>.env.<variable>` of each component whose compose service lists it |
| exposure | `components.jitsi-meet.service.type`, `components.jitsi-meet-jvb.service.type` |
| size of the claims `storage`, 1Gi | `components.jitsi-meet.volume_claims.storage.spec.resources.requests.storage`, the same below `jitsi-meet-prosody` |
| resources | `components.<c>.resources` |

Values of `env` are strings, so quote `"1"`. web resolves prosody by the
Service's full name, `jitsi-meet-prosody.<namespace>.svc.<cluster domain>`,
so set `applications.jitsi-meet.cluster_domain` on a cluster whose domain
is not `cluster.local`.

The images render their configuration at each start from the environment.
The directories `/config` of each image and `/prosody-plugins-custom` of
prosody take files that extend it, such as `custom-config.js` for web. A
target mounts a ConfigMap there through `config_maps` of the component.

## Mapping

The service `web` becomes the component `jitsi-meet`, `prosody`
`jitsi-meet-prosody`, `jicofo` `jitsi-meet-jicofo` and `jvb`
`jitsi-meet-jvb`. The compose file sets no variable of its own beyond
`SENTRY_DSN`. Its services pass variables from `.env`, which the
documentation copies from `env.example` at the same commit, SHA-256
`b38560d14b7f25be441f8ae116f13fcb626d8a3bd248c86f03ef25060d2330d9`
(DEC-306). A variable that `env.example` leaves unset is not rendered.

| Compose | Recipe |
|---|---|
| service `web` | StatefulSet `jitsi-meet`, Service `jitsi-meet` |
| service `prosody` | StatefulSet `jitsi-meet-prosody`, Service `jitsi-meet-prosody` |
| service `jicofo` | Deployment `jitsi-meet-jicofo`, Service `jitsi-meet-jicofo` |
| service `jvb` | Deployment `jitsi-meet-jvb`, Service `jitsi-meet-jvb` |
| images `${JITSI_IMAGE_REPO:-ghcr.io/jitsi}/<service>:stable-11248-3` | `ghcr.io/jitsi/<service>:stable-11248-3` with the digest of its index |
| ports `${HTTP_PORT}:8000` and `${HTTPS_PORT}:8443` of web, 8000 and 8443 in `env.example` | Service ports `http` 8000 and `https` 8443 |
| `expose` 5222, 5269, 5347 and 5280 of prosody | Service ports `c2s`, `s2s`, `component` and `http` |
| port `127.0.0.1:8888:8888` of jicofo | Service port `http` 8888 |
| ports `10000:10000/udp` and `127.0.0.1:8080:8080` of jvb | Service ports `media` 10000/UDP and `http` 8080 |
| `TZ` and the passwords in `env.example` | `TZ: UTC` in each `env`, `JICOFO_AUTH_PASSWORD` and `JVB_AUTH_PASSWORD` from the Secret `jitsi-meet` |
| `JIGASI_XMPP_PASSWORD`, `JIGASI_TRANSCRIBER_PASSWORD`, `JIBRI_RECORDER_PASSWORD`, `JIBRI_XMPP_PASSWORD` | not rendered. They serve jigasi and jibri, which `docker-compose.yml` does not run (DEC-306). |
| `SENTRY_DSN="${JICOFO_SENTRY_DSN:-0}"` and its jvb counterpart | `SENTRY_DSN: '"0"'`, the quoted value compose passes |
| prosody's network alias `${XMPP_SERVER:-xmpp.meet.jitsi}` | `XMPP_SERVER: jitsi-meet-prosody` for jicofo and jvb, and web's `XMPP_BOSH_URL_BASE` with the Service's full name (DEC-308) |
| bind mounts `${CONFIG}/storage/web` and `${CONFIG}/storage/prosody` | claim templates `storage`, `ReadWriteOnce`, 1Gi, at `/storage` and `/var/lib/prosody`, with `fsGroup: 1000` (DEC-307) |
| the other bind mounts below `${CONFIG}` | not rendered. The containers only read them, and the images have the directory empty or read it only for a feature that is off (DEC-307). |
| `read_only: true` | `readOnlyRootFilesystem: true` (DEC-309) |
| `tmpfs` at `/run` and `/tmp` | `emptyDir` volumes of `medium: Memory` with the compose sizes as `sizeLimit` (DEC-309) |
| `labels` `service: jitsi-<service>` | pod annotations |
| `restart`, `depends_on`, the network `meet.jitsi` | not rendered |
| not in the compose file | `ENABLE_AUTH` and `ENABLE_GUESTS` (DEC-310), the postStart hook and `MODERATOR_*` of prosody (DEC-311) |

Not every Service port answers with these settings, as with the compose
file. jicofo serves its REST API on 8888 at its loopback address unless
`JICOFO_ENABLE_REST` is set. prosody listens on 5269 only with
`PROSODY_ENABLE_S2S` and on 5347 only for an external component that its
configuration names.

## Proof

`check jitsi-meet --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests, with check 0.16.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38). `tests/target.yml` sets low-entropy test passwords.

`tests/smoke` starts a pod of prosody's image, which carries bash and curl.
From there, through the Services, it

- gets the start page of web on 8000 and on 8443, `/about/health` of jvb
  on 8080, and XMPP stream features from prosody on 5222
- requires that `meet.jitsi` offers no anonymous login, answers in-band
  registration with `service-unavailable` and refuses a wrong password,
  over BOSH through web
- waits until jicofo's REST API, on its loopback address, reports a
  bridge, because jicofo grants a meeting without one and then offers no
  session
- logs in as the moderator and as an anonymous guest, and requires that
  jicofo refuses the guest a new meeting
- has the moderator open a meeting and join its room, and the guest join it,
  each answering jicofo's disco#info query as a Jitsi client does
- requires jicofo's Jingle offer to the moderator, which names a UDP
  candidate on port 10000 at jvb's pod IP, so jicofo allocated the meeting
  on the bridge
- sends a message from the guest to the room and one from the moderator,
  and requires that each reaches the other
- stores private XML data as the moderator, deletes prosody's pod, logs in
  again once a new pod runs, gets a meeting from jicofo and reads the data
  back.

Not tested: audio and video, whether a client reaches UDP port 10000, ICE
through STUN, TURN, the web app in a browser, and the ports that answer
only with other settings.
