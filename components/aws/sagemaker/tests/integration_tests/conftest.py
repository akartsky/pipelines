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
import boto3
import kfp
import os
import utils

from datetime import datetime
from filelock import FileLock


def pytest_addoption(parser):
    parser.addoption(
        "--region",
        default="us-west-2",
        required=False,
        help="AWS region where test will run",
    )
    parser.addoption(
        "--role-arn", required=True, help="SageMaker execution IAM role ARN",
    )
    parser.addoption(
        "--s3-data-bucket",
        required=True,
        help="Regional S3 bucket name in which test data is hosted",
    )
    parser.addoption(
        "--minio-service-port",
        default="9000",
        required=False,
        help="Localhost port to which minio service is mapped to",
    )
    parser.addoption(
        "--kfp-namespace",
        default="kubeflow",
        required=False,
        help="Cluster namespace where kubeflow pipelines is installed",
    )


@pytest.fixture(scope="session", autouse=True)
def region(request):
    os.environ["AWS_REGION"] = request.config.getoption("--region")
    return request.config.getoption("--region")


@pytest.fixture(scope="session", autouse=True)
def role_arn(request):
    os.environ["ROLE_ARN"] = request.config.getoption("--role-arn")
    return request.config.getoption("--role-arn")


@pytest.fixture(scope="session", autouse=True)
def s3_data_bucket(request):
    os.environ["S3_DATA_BUCKET"] = request.config.getoption("--s3-data-bucket")
    return request.config.getoption("--s3-data-bucket")


@pytest.fixture(scope="session", autouse=True)
def minio_service_port(request):
    os.environ["MINIO_SERVICE_PORT"] = request.config.getoption("--minio-service-port")
    return request.config.getoption("--minio-service-port")


@pytest.fixture(scope="session", autouse=True)
def kfp_namespace(request):
    os.environ["NAMESPACE"] = request.config.getoption("--kfp-namespace")
    return request.config.getoption("--kfp-namespace")


@pytest.fixture(scope="session")
def boto3_session(region):
    return boto3.Session(region_name=region)


@pytest.fixture(scope="session")
def sagemaker_client(boto3_session):
    return boto3_session.client(service_name="sagemaker")


@pytest.fixture(scope="session")
def s3_client(boto3_session):
    return boto3_session.client(service_name="s3")


@pytest.fixture(scope="session")
def kfp_client():
    kfp_installed_namespace = utils.get_kfp_namespace()
    return kfp.Client(namespace=kfp_installed_namespace)


def get_experiment_id(kfp_client):
    exp_name = datetime.now().strftime("%Y-%m-%d-%H-%M")
    try:
        experiment = kfp_client.get_experiment(experiment_name=exp_name)
    except ValueError:
        experiment = kfp_client.create_experiment(name=exp_name)
    return experiment.id


@pytest.fixture(scope="session")
def experiment_id(kfp_client, tmp_path_factory, worker_id):
    if not worker_id:
        return get_experiment_id(kfp_client)

    # Locking taking as an example from
    # https://github.com/pytest-dev/pytest-xdist#making-session-scoped-fixtures-execute-only-once
    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "experiment_id"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = fn.read_text()
        else:
            data = get_experiment_id(kfp_client)
            fn.write_text(data)
    return data
