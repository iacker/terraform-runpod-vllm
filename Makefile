.PHONY: help key init plan apply ready test chat destroy fmt

help: ## Show this help
	@grep -E '^[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

key: ## Export RunPod API key from Vault into this shell (run: eval $$(make key))
	@echo "export TF_VAR_runpod_api_key=$$(VAULT_ADDR=http://127.0.0.1:8200 vault kv get -field=api_key hermes/runpod)"

test: ## Run the money-critical unit tests (no network)
	python3 test_runpod_create.py

fmt: ## terraform fmt
	terraform fmt

init: ## terraform init
	terraform init

plan: ## terraform plan
	terraform plan

apply: ## Create the pod (safe: idempotent, false-500 guarded, budget capped)
	terraform apply -auto-approve

ready: ## Wait until vLLM is actually serving (endpoint from tf output)
	./scripts/wait_ready.sh $$(terraform output -raw endpoint)

chat: ## Send a test prompt to the deployed model
	@curl -s $$(terraform output -raw endpoint)/v1/chat/completions \
	  -H "Content-Type: application/json" \
	  -d '{"model":"$(shell terraform output -raw endpoint >/dev/null 2>&1 && grep -m1 model terraform.tfvars 2>/dev/null | cut -d'"' -f2)","messages":[{"role":"user","content":"Say hello in one sentence."}],"max_tokens":60}' | python3 -m json.tool

destroy: ## Delete the pod to stop billing
	terraform destroy -auto-approve
