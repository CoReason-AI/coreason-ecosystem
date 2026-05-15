// Copyright (c) 2026 CoReason, Inc
//
// This software is proprietary and dual-licensed
// Licensed under the Prosperity Public License 3.0 (the "License")
// A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
// For details, see the LICENSE file
// Commercial use beyond a 30-day trial requires a separate license
//
// Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.8"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "ami_name" {
  type    = string
  default = "coreason-swarm-in-a-box-v1"
}

source "amazon-ebs" "ubuntu" {
  ami_name      = "${var.ami_name}-{{timestamp}}"
  instance_type = "t3.xlarge"
  region        = var.region

  source_ami_filter {
    filters = {
      name                = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["099720109477"] # Canonical
  }

  ssh_username = "ubuntu"
}

build {
  name    = "coreason-swarm"
  sources = [
    "source.amazon-ebs.ubuntu"
  ]

  provisioner "shell" {
    inline = [
      "echo 'Installing Docker...'",
      "sudo apt-get update",
      "sudo apt-get install -y ca-certificates curl gnupg",
      "sudo install -m 0755 -d /etc/apt/keyrings",
      "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
      "sudo chmod a+r /etc/apt/keyrings/docker.gpg",
      "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
      "sudo apt-get update",
      "sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
      "sudo usermod -aG docker ubuntu",
      "sudo systemctl enable docker",

      "echo 'Pulling CoReason Container Images...'",
      "sudo docker pull ghcr.io/coreason-ai/coreason-ecosystem:latest",
      "sudo docker pull ghcr.io/coreason-ai/coreason-runtime:latest"
    ]
  }

  provisioner "file" {
    source      = "../../../local/compose.yaml"
    destination = "/home/ubuntu/compose.yaml"
  }

  provisioner "shell" {
    inline = [
      "echo 'Setting up Cold Start Kit Service...'",
      "echo '[Unit]' | sudo tee /etc/systemd/system/coreason-swarm.service",
      "echo 'Description=CoReason Swarm-in-a-Box' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'After=docker.service' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'Requires=docker.service' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo '[Service]' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'Type=oneshot' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'RemainAfterExit=yes' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'WorkingDirectory=/home/ubuntu' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'ExecStart=/usr/bin/docker compose up -d' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'ExecStop=/usr/bin/docker compose down' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo '[Install]' | sudo tee -a /etc/systemd/system/coreason-swarm.service",
      "echo 'WantedBy=multi-user.target' | sudo tee -a /etc/systemd/system/coreason-swarm.service",

      "sudo systemctl enable coreason-swarm.service"
    ]
  }
}
