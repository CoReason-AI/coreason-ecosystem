import os

helm_dir = r'c:\files\git\github\coreason-ai\coreason-ecosystem\infrastructure\helm\coreason-enterprise'
values_path = os.path.join(helm_dir, 'values.yaml')

components = ['urnAuthority', 'metaEngineering', 'sensoryApp', 'sensoryEmbed', 'manifest']

values_additions = """
# Added Components
urnAuthority:
  replicaCount: 1
  image:
    repository: ghcr.io/coreason-ai/coreason-urn-authority
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 500m
      memory: 1Gi
    requests:
      cpu: 50m
      memory: 256Mi

metaEngineering:
  replicaCount: 1
  image:
    repository: ghcr.io/coreason-ai/coreason-meta-engineering
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 50m
      memory: 512Mi

sensoryApp:
  replicaCount: 1
  image:
    repository: ghcr.io/coreason-ai/coreason-sensory-app
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 50m
      memory: 128Mi

sensoryEmbed:
  replicaCount: 1
  image:
    repository: ghcr.io/coreason-ai/coreason-sensory-embed
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 50m
      memory: 128Mi

manifest:
  replicaCount: 1
  image:
    repository: ghcr.io/coreason-ai/coreason-manifest
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 200m
      memory: 256Mi
    requests:
      cpu: 10m
      memory: 64Mi
"""

with open(values_path, 'a') as f:
    f.write(values_additions)

template = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-__NAME__
  labels:
    app: __NAME__
spec:
  replicas: {{ .Values.__CAMEL__.replicaCount }}
  selector:
    matchLabels:
      app: __NAME__
  template:
    metadata:
      labels:
        app: __NAME__
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: __NAME__
          image: "{{ .Values.__CAMEL__.image.repository }}:{{ .Values.__CAMEL__.image.tag }}"
          imagePullPolicy: {{ .Values.__CAMEL__.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          resources:
            {{- toYaml .Values.__CAMEL__.resources | nindent 12 }}
          env:
            - name: COREASON_ENVIRONMENT
              value: {{ .Values.global.environment }}
            - name: COREASON_NETWORK_MODE
              value: {{ .Values.global.networkMode | default "public" }}
"""

for comp in components:
    name = comp.replace('urnAuthority', 'urn-authority').replace('metaEngineering', 'meta-engineering').replace('sensoryApp', 'sensory-app').replace('sensoryEmbed', 'sensory-embed').replace('manifest', 'manifest')
    content = template.replace("__NAME__", name).replace("__CAMEL__", comp)
    with open(os.path.join(helm_dir, 'templates', f'{name}-deployment.yaml'), 'w') as f:
        f.write(content)

print('Success')
