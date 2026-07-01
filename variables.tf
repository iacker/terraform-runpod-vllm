variable "runpod_api_key" {
  description = "RunPod REST API key. Prefer passing via TF_VAR_runpod_api_key from Vault, never hardcode."
  type        = string
  sensitive   = true
}

variable "pod_name" {
  description = "Name of the RunPod pod."
  type        = string
  default     = "tf-vllm"
}

variable "model" {
  description = "HuggingFace repo to serve with vLLM. Must be a stable-vLLM-supported arch (llama/qwen2/mistral)."
  type        = string
  default     = "NousResearch/Meta-Llama-3.1-8B-Instruct"
}

variable "gpu_type_ids" {
  description = "Ordered fallback list of RunPod GPU type IDs. First available is used."
  type        = list(string)
  default     = ["NVIDIA A40", "NVIDIA RTX A6000", "NVIDIA A100 80GB PCIe"]
}

variable "gpu_count" {
  description = "Number of GPUs."
  type        = number
  default     = 1
}

variable "container_disk_gb" {
  description = "Container disk size in GB. Must exceed model size + working space. No network volume (triggers false-500 bug)."
  type        = number
  default     = 120
}

variable "max_model_len" {
  description = "vLLM --max-model-len. Do not exceed the model's native context (max_position_embeddings)."
  type        = number
  default     = 16384
}

variable "vllm_image" {
  description = "vLLM container image. Use :latest for stable archs, :nightly only for bleeding-edge archs."
  type        = string
  default     = "vllm/vllm-openai:latest"
}

variable "max_cost_per_hr" {
  description = "Safety cap: if the created pod's costPerHr exceeds this, the deploy fails and deletes the pod. Protects budget."
  type        = number
  default     = 0.80
}
