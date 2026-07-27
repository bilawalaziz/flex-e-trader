# FlexeTrader Simple K8s Deploy

## Quick Start

```bash
# 1. Setup MicroK8s
microk8s enable dns storage ingress registry
microk8s config > ~/.kube/config

# 2. Build & push your app image
docker build -t localhost:32000/flexetrader-app:latest .
docker push localhost:32000/flexetrader-app:latest

# 3. Deploy via Helm
helm install flexetrader ./helm --create-namespace -n flexetrader

# OR via Terraform
cd terraform
terraform init
terraform apply

# 4. Access
# App:      http://<node-ip>:30800
# RabbitMQ: http://<node-ip>:31672  (guest/guest)
# Grafana:  http://<node-ip>:30300  (admin/admin)
```

## Update
```bash
helm upgrade flexetrader ./helm -n flexetrader
```

## Remove
```bash
helm uninstall flexetrader -n flexetrader
microk8s kubectl delete namespace flexetrader
```
