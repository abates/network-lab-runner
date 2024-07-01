## Helm Charts

```shell
helm repo add nautobot https://nautobot.github.io/helm-charts/
helm repo add jetstack https://charts.jetstack.io
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add traefik https://helm.traefik.io/traefik
helm repo update
```

## Install Components

1. Create digital ocean token secret in kubectl:
```shell
kubectl create namespace external-dns
kubectl --namespace external-dns create secret generic external-dns-token --from-literal digitalocean_api_token={{ env.DO_TOKEN }}
```

2. Install helm charts:
```shell
helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace -f cert-manager.yaml
kubectl apply -f cert-manager/traefik-certmanager.yaml
helm install external-dns bitnami/external-dns -f external-dns.yaml
helm install traefik traefik/traefik --namespace traefik --create-namespace -f traefik.yaml
helm install --namespace nautobot --create-namespace nautobot nautobot/nautobot -f nautobot.yaml
```

## Updating values

```shell
# example
helm --namespace cert-manager upgrade cert-manager bitnami/cert-manager -f cert-manager.yaml
helm --namespace external-dns upgrade external-dns bitnami/external-dns -f external-dns.yaml
helm --namespace traefik upgrade traefik traefik/traefik -f traefik.yaml
helm --namespace nautobot upgrade nautobot nautobot/nautobot -f nautobot.yaml
```

## Uninstalling

```shell
helm -n nautobot uninstall nautobot
helm -n traefik uninstall traefik
helm -n cert-manager uninstall cert-manager
helm -n external-dns uninstall external-dns
```

