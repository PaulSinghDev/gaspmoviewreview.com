import argparse
import paramiko
import tarfile
import os
import sys
import subprocess

## Setup an arg parser
arg_parser = argparse.ArgumentParser()

## Tell arg parser what we want args for
arg_parser.add_argument("--domain", help="The domain on which this will be deployed", required=True, type=str)
arg_parser.add_argument("--ip", "-i", help="The destination server IP", required=True, type=str)
arg_parser.add_argument("--port", "-p", help="The destination server port", required=True, type=int)
arg_parser.add_argument("--username", "-u", help="Username to authenticate a session in the destination server", required=True, type=str)
arg_parser.add_argument("--password", "-P", help="Password to authenticate a session in the destination server", required=True, type=str)
arg_parser.add_argument("--hash", "-H", help="The commit hash for this deployment", required=True, type=str)
arg_parser.add_argument("--sites-enabled", help="The path to the sites-enabled folder on the remote server", default="/etc/nginx/sites-enabled", required=False, type=str)
arg_parser.add_argument("--sites-available", help="The path to the sites-available folder on the remote server", default="/etc/nginx/sites-available", required=False, type=str)

## Get our args
args = arg_parser.parse_args()

deployment_path = f"/var/www/{args.domain}/deployments/{args.hash}"
deployment_domain_fragments = args.domain.split('.')[1:]
deployment_domain = f"{args.hash}"
for section in deployment_domain_fragments:
    deployment_domain = f"{deployment_domain}.{section}"

print(f"Starting deployment {args.hash} with domain: {deployment_domain}")

## Get some dirs
script_dir = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(script_dir, "..")
tar_path = os.path.join(root, f"{args.hash}.tar.gz")

print(f"Making archive in {tar_path}")

## Open a tar file
tar = tarfile.open(tar_path, "w:gz")

## Add the root folder to the tar
tar.add(os.path.abspath(root), arcname=".")

## Close the tar file
tar.close()

print(f"Finished making archive")
print(f"Connecting to {args.ip}")

## Copy it to the server
## Get a client
ssh = paramiko.SSHClient()
## Set known hosts
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
## Connect to the server
ssh.connect(hostname=args.ip,port=args.port,username=args.username,password=args.password)
## Open an FTP connection
sftp = ssh.open_sftp()

print("Connected to remote host")
print(f"Uploading tarball to /tmp/{args.hash}.tar.gz")

## Copy our tarball
sftp.put(tar_path, f"/tmp/{args.hash}.tar.gz")

print(f"Finished uploading tarball")
print(f"Creating deployment in /var/www/{args.domain}/deployments/{args.hash}")

## Array of commands to make on remote server
commands = [
    f"mkdir {deployment_path}",
    f"mv /tmp/{args.hash}.tar.gz {deployment_path}/{args.hash}.tar.gz",
    f"tar -xzf {deployment_path}/{args.hash}.tar.gz -C {deployment_path}",
    f"rm {deployment_path}/{args.hash}.tar.gz",
    f"cd {deployment_path}; ls scripts", 
    f"cd {deployment_path}; yarn install --frozen-lockfile",
    f"cd {deployment_path}; yarn build",
    f"cd {deployment_path}; python3 scripts/copyVirtualHost.py --domain {deployment_domain}", 
    f"cd {deployment_path}; pm2 yarn start --name {args.hash} -- start"
]
## Iterate them
for command in commands:
    ## Get thr response
    stdin, stdout, stderr = ssh.exec_command(command)
    ## Check if there was an error
    if stdout.channel.recv_exit_status() != 0:
        print(f"Error running command '{command}': {stderr.read().decode()}")
    else:
        print(f"Output of '{command}':\n{stdout.read().decode()}")


## Remove the tar
os.remove(tar_path)

print(f"Deployment {args.hash} created")

sftp.close()
ssh.close()

##subprocess.run(["scp", os.path.join(script_dir, "./copyVirtualHost.py"), "aumni@161.97.184.130:/tmp"])