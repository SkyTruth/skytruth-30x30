# Run with Terraform 1.6.4 from this module: terraform init && terraform test
# Plan only: no cloud credentials or deployed resources are needed.
provider "google" {
  project      = "invocation-test"
  region       = "us-east1"
  access_token = "unused-for-plan"
}

variables {
  project            = "invocation-test"
  region             = "us-east1"
  function_name      = "invocation-test"
  description        = "Invocation policy test"
  runtime            = "python313"
  entry_point        = "main"
  source_dir         = "."
  vpc_connector_name = "test-connector"
  additional_invokers = [
    "scheduler@invocation-test.iam.gserviceaccount.com",
    "tasks@invocation-test.iam.gserviceaccount.com",
  ]
}

run "private_by_default" {
  command = plan

  assert {
    condition = jsondecode(google_cloud_run_service_iam_policy.noauth.policy_data).bindings == [{
      role = "roles/run.invoker"
      members = [
        "serviceAccount:scheduler@invocation-test.iam.gserviceaccount.com",
        "serviceAccount:tasks@invocation-test.iam.gserviceaccount.com",
      ]
    }]
    error_message = "Only the Scheduler and Cloud Tasks identities should be able to invoke the private function."
  }
}

run "public_analysis_opt_in" {
  command = plan

  variables {
    allow_unauthenticated = true
    additional_invokers   = []
  }

  assert {
    condition = jsondecode(google_cloud_run_service_iam_policy.noauth.policy_data).bindings == [{
      role    = "roles/run.invoker"
      members = ["allUsers"]
    }]
    error_message = "Explicit public opt-in must preserve anonymous access for the analysis function."
  }
}
