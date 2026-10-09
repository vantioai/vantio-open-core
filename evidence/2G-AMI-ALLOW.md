# 2G Debian 12 image allow

Audience: INTERNAL_RESTRICTED
Date: 2026-10-08 (America/New_York)

The provision role keeps the Ubuntu allow `ami-0fa99aa8f97f9e30b`. This adds one current official Debian 12 amd64 image from owner `136693071363` in `us-east-2`. The id is chosen in CloudShell by `describe-images`. It is not hardcoded here.

`ec2:ReleaseAddress` is not removed from any deny, and no other action is widened.

## Lookup filter

```text
aws ec2 describe-images
  --region us-east-2
  --owners 136693071363
  --filters
    Name=name,Values=debian-12-amd64-20*
    Name=architecture,Values=x86_64
    Name=virtualization-type,Values=hvm
    Name=root-device-type,Values=ebs
    Name=state,Values=available
    Name=is-public,Values=true
```

The script then keeps images whose name is exactly `debian-12-amd64-YYYYMMDD-HHMM`, whose owner is `136693071363`, which are public EBS HVM amd64 images with no product code, and which have at least one EBS snapshot. It pins the newest `CreationDate`.

## Policy edit

The managed or inline policy on `vantio-w3-lab-provision` that already allows `arn:aws:ec2:us-east-2::image/ami-0fa99aa8f97f9e30b` is the only document edited. The Ubuntu statement is copied, not rewritten. The copy uses:

- Sid `RunDebian12PublicEbsImage`
- Resource `arn:aws:ec2:us-east-2::image/<debian ami>`
- `ec2:ImageID` set to that id
- `ec2:Owner` set to `136693071363`

Each EBS snapshot on that image gets its own `ec2:RunInstances` allow on `arn:aws:ec2:us-east-2::snapshot/<snap>`. A wildcard snapshot is not used. The previous policy version, or the inline document, is the rollback.

## Workflow input

`w3-lab-auto-provision.yml` and `w3-lab-auto-long-soak.yml` keep `image_id`. The default stays `ami-0fa99aa8f97f9e30b`. The sitting summary prints `workflow_image_id` for a 2G dispatch. `require_available_image` accepts that id when the described image is official Debian 12 from owner `136693071363`.
