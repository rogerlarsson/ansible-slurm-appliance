# Packer-based image build

This workflow uses Packer with `qemu-kvm` to build an image for a compute node based on a CentOS 8.2 cloud image. The same `ansible/site.yml` playbook is run inside Packer as for the normal cluster creation.

This image creation pipeline requires at least the control node to have been created using the normal ansible playbook.

Steps:

- Ensure hardware virtualisation is enabled:

      egrep 'vmx|svm' /proc/cpuinfo

- Follow the standard installation instructions in the main README.

- Install packer and qemu-kvm, and ensure libgcrypt is updated:

      sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
      sudo yum -y install packer
      sudo yum -y install qemu-kvm
      sudo yum -y install libgcrypt

- Activate the venv and the relevant environment.
- Ensure you have generated passwords using:

        ansible-playbook ansible/adhoc/generate-passwords.yml

- Ensure you have a public/private keypair as `~/.ssh/id_rsa[.pub]`.
- Create a config drive which sets this public key for the `centos` user, so that Packer can login to the VM:

        ansible-playbook packer/config-drive.yml # creates packer/config-drive.iso

- Build an image (using that config drive):

        mkfifo /tmp/qemu-serial.in /tmp/qemu-serial.out
        cd packer
        PACKER_LOG=1 packer build main.pkr.hcl
        # or during development:
        PACKER_LOG=1 packer build --on-error=ask main.pkr.hcl

  The following variables may also be set:

  - `disk_size`: Set the image size ([docs](https://www.packer.io/docs/builders/qemu#disk_size)). Defaults to 20G, so for smaller VMs use e.g: `packer build -var 'disk_size=10G' ...`
  - `groups`: List of ansible groups the packer VM is added to, to control which nodes to build an image for. Defaults to `["compute"]` to build a generic compute node image. The first element of this list is used as part of the image name.
  - `base_img_url`: URL or path of base image to use (default is CentOS 8.4 GenericCloud x86_64 image). See the Packer docs for [iso_url](https://www.packer.io/docs/builders/qemu#iso-configuration) details.
  - `base_img_checksum`: Checksum type:checksum for `base_img_url`.
  
  Examples:

     - Build an image for a login node: `packer build -var 'groups=["login"]' ...`

  Note the VM is also always added to the `builder` group to differentiate it from a real node - see developer notes below.

- For debugging, you can login to the VM over ssh by looking in the Packer output for lines showing the IP and ssh port forwarding, e.g.:

        Executing /usr/libexec/qemu-kvm: ...  "-netdev", "user,id=user.0,hostfwd=tcp::2922-:22", ... 

  so in this case login using:

        ssh -p 2922 centos@<ip address>

- You can also watch the console output from the VM startup in another terminal using:

        cat /tmp/qemu-serial.out

- The image will be created in `environments/<environment>/images`

- Upload the image to Openstack:

        openstack image create --file $PKR_VAR_environment_root/images/*.qcow2 --disk-format qcow2 $(basename $PKR_VAR_environment_root/images/*.qcow2)

You can now recreate the compute VMs with the new image e.g. by changing the compute image name in the deployment automation.
**NB:** You may need to restart `slurmctld` if the nodes come up and then go down again.

# Notes for developers

The Packer build VM is added to both the `builder` group and the groups specified in the packer `groups` variable, with the former allowing `environments/common/inventory/group_vars/builder/defaults.yml` to set variables specifically for the VM where the real cluster may not be contactable (depending on where the build is run from). Currently this means:
- Enabling but not starting `slurmd`.
- Setting NFS mounts to `present` but not `mounted`

Note that in this appliance the munge key is pre-created in the environment's "all" group vars, so this aspect needs no special handling.

Some more subtle points to note if developing code based off this:
- In general, we should assume that ansible needs to ssh proxy to the compute nodes via the control node (not actually the case in these demos as everything is on one network). However we **don't** want packer's "builder" host to use this proxy, so the proxy has to be added to the group `[${cluster_name}_compute:vars]`, not `[cluster_compute:vars]`.
- You can't use `-target` (terraform) and `--limit` (ansible) as the `openhpc` role needs all nodes in the play to be able to define `slurm.conf`. If you don't want to configure the entire cluster up-front then alternatives are:
  1. Define/create a smaller cluster in terraform/ansible, create that and build an image, then change the cluster definition to the real one, limiting the ansible play to just `cluster_login`.
  2. Work the other way around:
        - Create the control/login node using TF only (this would need the current inventory to be split up as currently the implicit dependency on `computes` will create those too, even with `-limit`).
        - Build the image.
        - Launch compute nodes w/ TF using that (slurm won't start).
        - Configure control node using `--limit` (will use the local munge key).
