import base64
import pulumi
from typing import Any


class PulumiMocks(pulumi.runtime.Mocks):
    def new_resource(
        self, args: pulumi.runtime.MockResourceArgs
    ) -> tuple[str | None, dict[Any, Any]]:
        if args.typ == "aws:ec2/spotInstanceRequest:SpotInstanceRequest":
            return (args.name + "_id", dict(args.inputs, public_ip="203.0.113.1"))
        return (args.name + "_id", args.inputs)

    def call(
        self, args: pulumi.runtime.MockCallArgs
    ) -> tuple[dict[Any, Any], list[tuple[str, str]] | None]:
        return ({}, None)


@pulumi.runtime.test  # type: ignore
def test_aws_spot_deployment_logic() -> None:
    pulumi.runtime.set_mocks(PulumiMocks())

    # The config expects keys without namespace if using simple config or with namespace if specified.
    # Since in __main__.py the config is `pulumi.Config()`, we need to use the project name or default.
    pulumi.runtime.set_all_config(
        {
            "project:instance_type": "t3.micro",
            "project:ami_id": "ami-12345",
            "project:ssh_pub_key": "ssh-rsa AAA...",
            "project:boot_payload_b64": base64.b64encode(b"payload").decode("utf-8"),
            "instance_type": "t3.micro",
            "ami_id": "ami-12345",
            "ssh_pub_key": "ssh-rsa AAA...",
            "boot_payload_b64": base64.b64encode(b"payload").decode("utf-8"),
        }
    )

    # Test the deployment logic by importing the module
    import infrastructure.ephemeral.aws_spot.__main__ as aws_spot_module

    def check_instance_type(args: list[str]) -> None:
        assert args[0] == "t3.micro"

    pulumi.Output.all(aws_spot_module.spot_instance_request.instance_type).apply(check_instance_type)  # type: ignore[attr-defined]
