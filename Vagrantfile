
Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  #config.vm.box = "puppetlabs/centos-7.0-64-nocm"
  config.vm.box = "bento/centos-7.2"

  # Disable automatic box update checking. If you disable this, then
  # boxes will only be checked for updates when the user runs
  # `vagrant box outdated`. This is not recommended.
  # config.vm.box_check_update = false

  # forward port 5020 on the localhost to port 80 in the guest
  config.vm.network "forwarded_port", guest: 80, host: 5020
  #config.vm.network "forwarded_port", guest: 3306, host: 3306

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  config.vm.synced_folder ".", "/srv/www/rq"

  config.vm.define :rq

#  if ARGV[1] and (ARGV[1].split('=')[0] == "--provider" or ARGV[2])
#    provider = (ARGV[1].split('=')[1] || ARGV[2])
#  else
#    provider = (ENV['VAGRANT_DEFAULT_PROVIDER'] || :virtualbox).to_sym
#  end

#  if provider == "virtualbox"
#    config.vm.provider "virtualbox" do |v|
#      # 2GB memory for virtualbox
#      v.memory = 2048
#    end
#  end

#  if provider == "vmware_fusion"
    config.vm.provider "vmware_fusion" do |v|
      # 2GB memory for vmware fusion
      v.vmx["memsize"] = "2048"
      v.name = "rq"
    end
#  end

  config.vm.post_up_message = "rq is available at http://localhost:5000; to start it 'cd /srv/www/rq/rq; ./run.py'.  NOTE: you must first run /home/vagrant/mysql-setup.sh to setup MySQL."

  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "provisioning/main.yml"
  end
end
