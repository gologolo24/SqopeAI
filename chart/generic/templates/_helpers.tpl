{{/*
Resource name: the Helm release name (ArgoCD sets it to the service name, e.g. "user-service").
*/}}
{{- define "generic.fullname" -}}
{{- default .Release.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "generic.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "generic.selectorLabels" -}}
app.kubernetes.io/name: {{ include "generic.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "generic.labels" -}}
helm.sh/chart: {{ include "generic.chart" . }}
{{ include "generic.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | trunc 63 | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: sqope-ai
{{- end -}}

{{- define "generic.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- include "generic.fullname" . -}}
{{- else -}}
default
{{- end -}}
{{- end -}}

{{- define "generic.image" -}}
{{- $repo := required "image.repository is required" .Values.image.repository -}}
{{- $tag := required "image.tag is required (the git commit SHA)" .Values.image.tag -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}
