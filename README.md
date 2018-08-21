# Ansible role: K8s

This role renders an arbitrary number of [Jinja2](http://jinja.pocoo.org/) templates and deploys or removes them to/from Kubernetes cluster.


[![Build Status](https://travis-ci.org/cytopia/ansible-role-k8s.svg?branch=master)](https://travis-ci.org/cytopia/ansible-role-k8s)
[![Version](https://img.shields.io/github/tag/cytopia/ansible-role-k8s.svg)](https://github.com/cytopia/ansible-role-k8s/tags)


## Requirements

* Ansible 2.5
* [openshift](https://pypi.org/project/openshift/) Python package


## Command line variables

Additional variables that can be used (either as `host_vars`/`group_vars` or via command line args):

| Variable      | Description                  |
|---------------|------------------------------|
| `k8s_create`  | If set with any value, only deployments to create are executed. |
| `k8s_remove`  | If set with any value, only deployments to remove are executed. |
| `k8s_context` | Global cluster context (can be overwritten by each array item). |
| `k8s_tag`     | Only deployments (create or remove) which have this tag specified in their definition are executed. |
| `k8s_force`   | Force deployment. The existing object will be replaced. |


## Example

For all examples below, we will use the following Ansible playbook:

**`playbook.yml`**
```yaml
---
- hosts: all
  roles:
    - k8s
  tags:
    - k8s
```


### 1. Usage of variables

**Required files:**

**`create-k8s-namespace.yml.j2`**
```yml
---
kind: Namespace
apiVersion: v1
metadata:
  name: {{ my_namespace }}
  labels:
    name: {{ my_namespace }}
```

**`group_vars/all.yml`**
```yaml
---
# Custom variables for usage in templates
my_namespace: frontend

# Role variables
k8s_templates_create:
  - template: path/to/create-k8s-namespace.yml.j2
```

**How to execute:**
```bash
# Deploy namespace
$ ansible-playbook playbook.yml

# Overwrite namespace name
$ ansible-playbook playbook.yml -e my_namespace=backend
```

### 2. Usage of tags per item

**Required files:**

**`group_vars/all.yml`**
```yaml
---
k8s_templates_create:
  - template: path/to/pod1.yml.j2
    tag: stage1
  - template: path/to/pod2.yml.j2
    tags:
      - pod
      - stage2

k8s_templates_remove:
  - template: path/to/ds1.yml.j2
    tag: stage1
  - template: path/to/ds2.yml.j2
    tags:
      - pod
      - stage2
```

**How to execute:**
```bash
# Remove and deploy all files
$ ansible-playbook playbook.yml

# Only deploy files
$ ansible-playbook playbook.yml -e k8s_create=1

# Only deploy files with tag stage1
$ ansible-playbook playbook.yml -e k8s_create=1 -e k8s_tag=stage1
```

### 3. Usage of context per item

**Required files:**

**`group_vars/all.yml`**
```yaml
---
# context is global for all deployment files
k8s_context: minikube

k8s_templates_create:
  - template: path/to/pod1.yml.j2
  - template: path/to/pod2.yml.j2
  # The next item uses a different context (takes precedence over global context)
  - template: path/to/pod3.yml.j2
    context: dev-cluster
```

**How to execute:**
```bash
# IMPORTANT:
# When a context is attached to an item (as with pod3.yml)
# it will take precedence over any globally specified context.
# So this example will deploy everything into the cluster specified by the global context,
# except pod3.yml, which will always go into dev-cluster

# Deploy everything into minikube (pod3.yml will however be deployed into dev-cluster)
$ ansible-playbook playbook.yml -e k8s_create=1

# Deploy everything into a different cluster (pod3.yml will however be deployed into dev-cluster)
$ ansible-playbook playbook.yml -e k8s_create=1 -e k8s_context=prod-cluster
```

## Testing

#### Requirements

* Docker
* [yamllint](https://github.com/adrienverge/yamllint)
* [openshift](https://pypi.org/project/openshift/) Python package


#### Run tests

```bash
# Lint the source files
make lint

# Run integration tests with default Ansible version
make test

# Run integration tests with custom Ansible version
make test ANSIBLE_VERSION=2.6
```
