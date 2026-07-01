output "pod_id" {
  description = "RunPod pod ID."
  value       = data.external.vllm_pod.result.pod_id
}

output "endpoint" {
  description = "OpenAI-compatible base URL. Append /v1/models or /v1/chat/completions."
  value       = data.external.vllm_pod.result.endpoint
}

output "cost_per_hr" {
  description = "Actual billed cost per hour of the created pod."
  value       = data.external.vllm_pod.result.cost_per_hr
}

output "status" {
  description = "Pod desired status (RUNNING means container started, NOT that vLLM finished loading)."
  value       = data.external.vllm_pod.result.status
}

output "readiness_hint" {
  description = "How to check the model is actually serving."
  value       = "Poll ${data.external.vllm_pod.result.endpoint}/v1/models until HTTP 200 (vLLM loads in 5-15 min). Use: ./scripts/wait_ready.sh ${data.external.vllm_pod.result.endpoint}"
}
