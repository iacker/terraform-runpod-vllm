# -----------------------------------------------------------------------------
# RunPod vLLM pod — provisioned via a safe external script that guards against
# RunPod's false-500 bug (POST returns 500 but still creates the pod).
# The provider-native runpod/runpod is too immature (no resource docs, no
# false-500 handling) to trust with billed GPU, so we wrap the REST API.
# -----------------------------------------------------------------------------

data "external" "vllm_pod" {
  program = ["python3", "${path.module}/scripts/runpod_create.py"]

  query = {
    runpod_api_key    = var.runpod_api_key
    pod_name          = var.pod_name
    model             = var.model
    gpu_type_ids      = jsonencode(var.gpu_type_ids)
    gpu_count         = tostring(var.gpu_count)
    container_disk_gb = tostring(var.container_disk_gb)
    max_model_len     = tostring(var.max_model_len)
    vllm_image        = var.vllm_image
    max_cost_per_hr   = tostring(var.max_cost_per_hr)
  }
}

# Carries the pod id into the destroy phase so we can delete the pod (stop
# billing) on `terraform destroy`. The API key is passed to the destroy script
# via an env var, never on the command line, so it never leaks into logs.
locals {
  # path.module is not available in a destroy provisioner (self-only rule), so
  # capture the script path and key into the resource input up front.
  destroy_script = "${path.module}/scripts/runpod_destroy.sh"
}

resource "terraform_data" "pod_lifecycle" {
  # Everything the destroy provisioner needs must live in `input` (self-only).
  input = {
    pod_id  = data.external.vllm_pod.result.pod_id
    api_key = var.runpod_api_key
    script  = local.destroy_script
  }

  provisioner "local-exec" {
    when    = destroy
    command = "${self.input.script} ${self.input.pod_id}"
    environment = {
      RUNPOD_API_KEY = self.input.api_key
    }
  }
}
