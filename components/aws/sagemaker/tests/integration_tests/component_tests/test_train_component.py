# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import pytest
import os
import json
import utils
from utils import kfp_client_utils
from utils import minio_utils
from utils import sagemaker_utils


@pytest.mark.parametrize(
    "test_file_dir",
    [
        pytest.param(
            "resources/config/simple-mnist-training", marks=pytest.mark.canary_test
        )
    ],
)
def test_trainingjob(
    kfp_client, experiment_id, region, sagemaker_client, test_file_dir
):

    download_dir = utils.mkdir(os.path.join(test_file_dir + "/generated"))
    test_params = utils.load_params(
        utils.replace_placeholders(
            os.path.join(test_file_dir, "config.yaml"),
            os.path.join(download_dir, "config.yaml"),
        )
    )

    test_params["Arguments"]["hyperparameters"] = json.dumps(
        test_params["Arguments"]["hyperparameters"]
    )
    test_params["Arguments"]["channels"] = json.dumps(
        test_params["Arguments"]["channels"]
    )
    _, _, workflow_json = kfp_client_utils.compile_run_monitor_pipeline(
        kfp_client,
        experiment_id,
        test_params["PipelineDefinition"],
        test_params["Arguments"],
        download_dir,
        test_params["TestName"],
        test_params["Timeout"],
    )

    outputs = {
        "sagemaker-training-job": ["job_name", "model_artifact_url", "training_image"]
    }
    output_files = minio_utils.artifact_download_iterator(
        workflow_json, outputs, download_dir
    )

    # Verify Training job was successful on SageMaker
    training_job_name = utils.read_from_file_in_tar(
        output_files["sagemaker-training-job"]["job_name"], "job_name.txt"
    )
    print(f"training job name: {training_job_name}")
    train_response = sagemaker_utils.describe_training_job(
        sagemaker_client, training_job_name
    )
    assert train_response["TrainingJobStatus"] == "Completed"

    # Verify model artifacts output was generated from this run
    model_artifact_url = utils.read_from_file_in_tar(
        output_files["sagemaker-training-job"]["model_artifact_url"],
        "model_artifact_url.txt",
    )
    print(f"model_artifact_url: {model_artifact_url}")
    assert model_artifact_url == train_response["ModelArtifacts"]["S3ModelArtifacts"]
    assert training_job_name in model_artifact_url

    # Verify training image output is an ECR image
    training_image = utils.read_from_file_in_tar(
        output_files["sagemaker-training-job"]["training_image"], "training_image.txt",
    )
    print(f"Training image used: {training_image}")
    if "ExpectedTrainingImage" in test_params.keys():
        assert test_params["ExpectedTrainingImage"] == training_image
    else:
        assert f"dkr.ecr.{region}.amazonaws.com" in training_image

    utils.remove_dir(download_dir)
