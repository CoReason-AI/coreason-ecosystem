import os

helm_dir = r'c:\files\git\github\coreason-ai\coreason-ecosystem\infrastructure\helm\coreason-enterprise'

components = ['urnAuthority', 'metaEngineering', 'sensoryApp', 'sensoryEmbed', 'manifest']

template = """apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-__NAME__
  labels:
    app: __NAME__
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    app: __NAME__
"""

for comp in components:
    name = comp.replace('urnAuthority', 'urn-authority').replace('metaEngineering', 'meta-engineering').replace('sensoryApp', 'sensory-app').replace('sensoryEmbed', 'sensory-embed').replace('manifest', 'manifest')
    content = template.replace("__NAME__", name).replace("__CAMEL__", comp)
    with open(os.path.join(helm_dir, 'templates', f'{name}-service.yaml'), 'w') as f:
        f.write(content)

print('Success')
