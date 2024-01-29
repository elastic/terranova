# Terranova

*Terranova is a thin wrapper for Terraform that provides extra tools and logic to handle Terraform configurations at scale.*

* [Source](https://github.com/elastic/terranova)
* [Documentation](https://github.com/elastic/terranova)
* [Issues](https://github.com/elastic/terranova/issues)
* [Contact](mailto:adrien.mannocci@elastic.co)

## Prerequisites

* [Python 3.11+](https://docs.python.org/3/) for development.
* [Poetry](https://python-poetry.org/) for build system.
* [Podman](https://podman.io/docs) for container packaging.
* [pre-commit](https://pre-commit.com/) for git management.

## Motivation & Context

* We needed a way to manage resources as code at scale.
* The solution should leverage terraform to avoid re-implementing the wheel.
* The solution shouldn't leverage the terraform configuration DSL to add features since it can change.

## Features

* Ability to share terraform configuration without modules.
* Ability to define arbitrary resource layout.
* Ability to auto-generate documentation using metadata attached to resource definition.
* Ability to execute runbooks to interact with resources.
* Ability to import variables between resource group.

## Workflow

### Setup

The following steps will ensure your project is cloned properly.

1. Clone repository:
   ```shell
   git clone https://github.com/elastic/terranova
   cd terranova
   ```
2. Use version defined in .python-version:
   ```shell
   pyenv install
   ```
3. Install dependencies and setup environment:
   ```shell
   poetry install
   poetry shell
   poetry poe env:configure
   ```

### Lint

* To lint you have to use the workflow.

```bash
poetry poe lint
```

* It will lint the project code using `pylint`.

### Format

* To format you have to use the workflow.

```bash
poetry poe fmt
```

* It will format the project code using `black` and `isort`.

## Usage

### Define an arbitrary resource layout

* `terranova` rely on the concept of resource groups.
* You can define as many resource groups as you want.
* The base layout should contain the directory `resources` and `shared`.
* The `resources` directory contains resource groups.
* The `shared` directory contains any sharable resource that will be symlink if defined as dependency.
* A resource group is defined when a `manifest.yml` is present.
* By default, `terranova` will look for a `conf` directory in the working directory that contain both above directories.

```
conf
├── resources
│   ├── resource_group_1
│   │   ├── runbooks
│   │   │   └── pyinfra.py
│   │   ├── main.tf
│   │   └── manifest.yml
│   └── resource_group_2
│       ├── main.tf
│       └── manifest.yml
└── shared
    ├── providers
    │   └── github.tf
    └── config.tf
```

* `terranova` will rely on the layout to apply change using terraform.
* In the above case, running `terranova apply resource_group_1` will run `terraform` on resources present in that directory.
* `terranova` supports any depth within the layout.
* This allows you to reflect any structure.

### How to get start

* Create a new directory in `conf/resources`.
* Create a new `manifest.yml` file with the following content.

```yaml
version: '1.2'

metadata:
  name: Terranova Hello World
  description: Hello World
  url: https://github.com/elastic/terranova
  contact: mailto:adrien.mannocci@elastic.co
```

* Define any resource using standard `terraform` configuration.
* Add metadata on each resource to allow auto-generate documentation.

```terraform
/*
@attr-name attr-value
*/
resource "null_resource" "foobar" {}
```

* You can now run `terranova init <resource_group_name>` and `terranova apply <resource_group_name>`.

### How to define shared dependencies.

* In some case, we need to share common terraform configuration or scripts across many resource group.
* It's possible to define dependencies in the manifest and symlink them in any resource group.
* Those common resources should be defined in the `shared` directory.
* All symlink are maintained by `terranova` and are updated when the `terranova init` command is run.

```yaml
# Supported since 1.0 manifest version.

...
dependencies:
  - source: providers/github.tf   # Which file or directory to symlink.
    target: 00-github-provider.tf # Where to symlink the file or directory.
...
```

### How to define runbook.

* In some case, we need to interact with terraform resources using specific tooling.
* It's possible to define a runbook in the manifest and invoke arbitrary tools.
* It's also possible to interact with `terranova` to extract information using [`outputs`](https://developer.hashicorp.com/terraform/language/values/outputs).

```yaml
# Supported since 1.1 manifest version.

...
runbooks:
  - name: "<runbook_name>" # Used as argument in the command
    entrypoint: "<tool_entrypoint>" # Tool to invoke
    workdir: "<working_directory>" # Optional: Used to navigate in sub-directories.
    args:
      - <arguments> # List of arguments to pass
    env:
      - name: PATH # Inherit environment value
      - name: FOO  # Override or define environment value
        value: bar
...
```

### How to import variables across resource groups.

* In some case, we need to interact across many resource groups and need to import variables from a resource group to another one.
* It's possible to define imports in the manifest.

```yaml
# Supported since 1.2 manifest version.

...
imports:
  - from: "<resource_group_path>" # Relative resource group path
    import: "<output_variable>" # Name of the output variable to import
    as: "<working_directory>" # Optional: Name of the input variable to map to.
...
```

### How to regenerate the documentation.

* Run the following command `terranova docs`.

### How to apply configuration changes.

* Run the following command `terranova apply <path>`.

### How to import a resource.

* Run the following command `terranova import <path> <resource_address> <identifier>`.
* The [`import`](https://developer.hashicorp.com/terraform/cli/import) terraform command is used under the hood.

## Roadmap

* Implement a command to move states on remote backend to match the resource layout after a refactor.
* Add e2e tests.

## Contributing

If you find this image useful here's how you can help :

* Send a Pull Request with your awesome new features and bug fixed.
* Be part of the community and help resolve [Issues](https://github.com/elastic/terranova/issues).
