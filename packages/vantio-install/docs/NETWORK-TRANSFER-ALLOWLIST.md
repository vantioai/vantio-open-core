# Network transfer allowlist

This page tells a qualified Linux operator how to copy one sealed Phantom Engine archive onto the customer host that will keep the node. You already hold the archive on the operator workstation. The installer reads the bundle on that host. It does not fetch the archive.

The copy uses a temporary allow from one operator address, or from a bastion range the customer already operates. You remove that allow after the checksum succeeds and the file is in place. This page does not publish the archive, and it does not add the archive bytes to the repository.

Recorded status: `published` is false. The claim ceiling is `INTERNAL_CLEAN_HOST_PROOF`. `proof_state` stays `NOT_PROVED`. This note does not record a LIVE_TRANSFER PASS. Gap `GAP-CB-DEP-013` stays open.

## Origin

Origin is the sealed archive already on the operator workstation, in a directory you choose on that workstation. The source commit recorded for that archive is `fab81efc08110506ff90847495197e7051a253b5`. That commit is an identity pin. This page does not tell you to obtain the bytes from a repository checkout or from a container registry.

This repository does not contain the archive. If the file is not already on the workstation, stop. Do not upload the archive to create a copy, and do not publish a download URL for it.

## Identity

Use this basename exactly. Do not shorten it, and do not drop `customer-staging` from the name. Do not substitute another file and keep this name.

- Basename: `vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar`
- Relative path after placement: `artifacts/phantom-engine/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar`
- SHA-256: `72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128`
- Source commit: `fab81efc08110506ff90847495197e7051a253b5`
- Manifest digest: `sha256:4d932b93bf4c20983142d5f9bff1ea060d9407a19a5e8c9f59db29f7a4122553`
- `published` is false

This procedure does not change frozen versions. Optics CLI stays 0.3.24. Agent SDK npm stays 0.2.4. Agent SDK Python stays 3.1.0. The source commit, SHA-256, and manifest digest stay the values above.

The staging checksum line is the digest, two spaces, then the basename:

```text
72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128  vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar
```

The bundle checksum line is the same digest, two spaces, then the relative path:

```text
72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128  artifacts/phantom-engine/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar
```

## Hash verify

On the workstation, in the directory that already holds the archive and `SHA256SUMS`, verify before you open a network allow. Both commands must exit 0. The first command checks the locked digest from this page. The second checks the staging `SHA256SUMS`. `sha256sum` is the last command in the pipeline, so a mismatch still exits non-zero.

```bash
echo "72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128  vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar" | sha256sum -c -
sha256sum -c SHA256SUMS
```

Each output must show `vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar: OK`. The staging `SHA256SUMS` must contain the staging line in the identity section. A checksum file that matches the bytes but not the locked digest is a hash mismatch.

If the archive is missing, stop. If `SHA256SUMS` is missing, stop. If the digest does not match, that is a hash mismatch. Stop. Do not open the allow, and do not copy the file.

Do not edit the archive. Do not change the digest so a failed check prints OK. A hand-edited archive is not a successful handoff.

## Transfer boundary

You open the allow in the customer cloud account, on the customer security group, for the customer host. Replace `OPERATOR_PUBLIC_IP` with the operator workstation public IPv4 address. Replace `CUSTOMER_SG_ID` with the customer security group id. Replace `CUSTOMER_HOST` with the customer host name or address. Replace `SSH_IDENTITY` with the key you already use from that workstation. Those four tokens are placeholders. This page does not ship a key, a group id, or an address.

Authorize TCP port 22 from `OPERATOR_PUBLIC_IP/32` only. A bastion range the customer already operates can stand in for that single address when the copy is made from the bastion. Do not authorize SSH or SCP from every source address. An allow rule that wide is refused. The allow exists for this copy. You revoke it in the last step.

The same boundary works on a firewall that is not AWS. Allow TCP port 22, or the SCP port the customer already uses, from that same single operator address. Then copy, verify, place, and remove the allow.

## Destination

The destination is the bundle directory already on the customer host. This page calls that directory `./bundle/` relative to the login directory you use for the copy. The archive lands at `artifacts/phantom-engine/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar` under that bundle. The bundle `SHA256SUMS` stays at the bundle root.

Do not replace the bundle `SHA256SUMS` with the staging checksum file. The staging file names the basename beside the archive. The bundle file names the relative path. Both lines carry the same digest. If the bundle file is missing, stop. If the bundle line is missing, or the digest on that line differs, stop. Do not write a new digest to force a match, and do not create `MANIFEST.json` from this page.

This note does not rename the archive, and it does not change the installer's frozen pins. If `vantio-install plan` stops because it does not see this basename, stop. Leave the sealed file in place under the relative path above. Do not rename it so the plan will continue.

## Worked handoff

Run these steps in order. Run a later step only when the previous command exits 0. The success path is allow, then copy, then verify, then place, then revoke.

```bash
# 1. ALLOW
aws ec2 authorize-security-group-ingress \
  --group-id CUSTOMER_SG_ID \
  --ip-permissions '[
    {
      "IpProtocol": "tcp",
      "FromPort": 22,
      "ToPort": 22,
      "IpRanges": [{
        "CidrIp": "OPERATOR_PUBLIC_IP/32",
        "Description": "temp-vantio-sealed-media-scp"
      }]
    }
  ]'

# 2. COPY
ssh -i SSH_IDENTITY ubuntu@CUSTOMER_HOST 'mkdir -p ./vantio-sealed-media'
scp -i SSH_IDENTITY \
  ./vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar \
  ./SHA256SUMS \
  ubuntu@CUSTOMER_HOST:./vantio-sealed-media/

# 3. VERIFY
ssh -i SSH_IDENTITY ubuntu@CUSTOMER_HOST \
  'cd ./vantio-sealed-media && \
   echo "72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128  vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar" | sha256sum -c - > ./transfer-verify.txt && \
   sha256sum -c SHA256SUMS >> ./transfer-verify.txt'

# 4. PLACE
ssh -i SSH_IDENTITY ubuntu@CUSTOMER_HOST \
  'grep -F "72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128  artifacts/phantom-engine/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar" ./bundle/SHA256SUMS && \
   mkdir -p ./bundle/artifacts/phantom-engine && \
   mv ./vantio-sealed-media/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar \
      ./bundle/artifacts/phantom-engine/'

# 5. REVOKE
aws ec2 revoke-security-group-ingress \
  --group-id CUSTOMER_SG_ID \
  --protocol tcp --port 22 --cidr OPERATOR_PUBLIC_IP/32
```

After verify exits 0, read `./vantio-sealed-media/transfer-verify.txt` on the customer host. It must contain `vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar: OK` for the locked digest and for `SHA256SUMS`. If verify exits non-zero, do not place the archive. Keep the transcript if it was written. Revoke the temporary allow. The checksum command stays at the end of its pipeline, and the shell uses `&&`, so a mismatch does not continue. Do not pipe `sha256sum -c` into `tee` or any later command that would hide a non-zero exit.

Place checks the bundle checksum line before it moves the file. If that grep exits non-zero, the archive stays in `./vantio-sealed-media/` and you do not treat the handoff as complete. Revoke the temporary allow.

## Failure behavior

Each case below stops the handoff. You do not place the archive into `artifacts/phantom-engine/` after a failure. If the temporary allow is already open, revoke it before you leave.

- The archive is missing. Stop. Do not copy an empty path.
- `SHA256SUMS` is missing on the workstation or on the customer host. Stop.
- The digest does not match `72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128`. That is a hash mismatch. Stop. A `SHA256SUMS` file that matches some other bytes, and not the locked digest, stops the handoff the same way.
- A different source commit, a different SHA-256, or a different manifest digest is the wrong version. Optics CLI 0.3.24, Agent SDK npm 0.2.4, and Agent SDK Python 3.1.0 stay as they are. Stop. Do not rename the other file to this basename.
- An archive whose name is not linux-amd64, or a host that is not x86_64, is the wrong architecture. Stop. Do not rename the file so the name says linux-amd64.
- The copy is incomplete. The destination file is shorter than the sealed original, or `sha256sum -c` did not exit 0. Stop. Do not place an incomplete file.
- The bundle `SHA256SUMS` line is missing or carries a different digest. Stop. Do not write a replacement digest.

`vantio-install plan` remains the installer check after a completed handoff. A stopped plan is a stop. It is not a prompt to repair the bytes.

## Recovery

This recovery is for the copy. It does not resume an installer transaction.

If the copy is interrupted, treat the destination file as incomplete. Delete that partial file from `./vantio-sealed-media/` and from `artifacts/phantom-engine/` if a partial file reached either place. Do not move an incomplete file into `artifacts/phantom-engine/`. Do not resume an incomplete file into that directory.

Copy the full sealed archive again from the workstation original. Run `sha256sum -c SHA256SUMS` again. Place the archive only after that command exits 0 and the transcript shows OK for this basename. Then revoke the allow. If you will not retry, revoke the allow now and leave the bundle unchanged.

Do not edit the archive, splice it, or pad it. Do not change the digest so the check prints OK. There is no repair that ends in a successful handoff. A failed checksum ends in a deleted failed copy, or in a new full copy that verifies. Nothing else counts as recovery.

## Evidence export

On the customer host, verify writes `./vantio-sealed-media/transfer-verify.txt`. That file is the checksum transcript. Keep it. Also write `transfer-evidence.txt` next to it with these lines:

```text
basename: vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar
relative: artifacts/phantom-engine/vantio-phantom-engine-customer-staging-fab81efc0811-linux-amd64.oci.tar
sha256: 72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128
source_commit: fab81efc08110506ff90847495197e7051a253b5
manifest_digest: sha256:4d932b93bf4c20983142d5f9bff1ea060d9407a19a5e8c9f59db29f7a4122553
published: false
claim_ceiling: INTERNAL_CLEAN_HOST_PROOF
gap: GAP-CB-DEP-013
live_transfer: none
```

Keep `transfer-verify.txt` and `transfer-evidence.txt` with the bundle. When the installer writes the evidence directory, copy both files into that directory next to `PLAN.json` and `PREFLIGHT.json`. Do not upload either file. The transcript records the checksum result. A line that does not show OK is a stop, and you keep it as the record of that stop. This note does not record a LIVE_TRANSFER PASS.
