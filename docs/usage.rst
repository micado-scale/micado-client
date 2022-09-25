Getting Started
===============

Dependencies
~~~~~~~~~~~~
The required Python packages are defined under the ``requirements.txt``. Make sure to
install those before using MiCADO client library. For reference, they are:

.. code-block::

  requests==2.24.0
  ruamel.yaml==0.16.10
  pycryptodome==3.9.8
  python-novaclient==17.2.0
  openstacksdk==0.48.0
  ansible==2.10.0

Get the Library
~~~~~~~~~~~~~~~
Currently, the library is available directly from github.

Simply clone the respository and add the location to your PYTHONPATH

.. code-block:: console

  $ MC_PATH="/usr/local/lib/micado-client"
  $ git clone https://github.com/micado-scale/micado-client $MC_PATH
  $ export PYTHONPATH="$PYTHONPATH:$MC_PATH"
  $ mkdir -p ~/.micado-cli
  $ touch ~/.micado-cli/credentials-cloud-api.yml

Specify cloud credentials
~~~~~~~~~~~~~~~~~~~~~~~~~
Specify cloud credential for the MiCADO cluster creation. Please,
edit ``~/.micado-cli/credentials-cloud-api.yml``

.. code-block:: yaml

    pre_authentication:
    - type: openid
    auth_data: &OPENID
        # Use this anchor for generating OpenID Connect access tokens (see nova)
        url:
        client_id:
        client_secret:
        refresh_token:

    resource:
    - type: cloudbroker
    auth_data:
        email: 
        password: 

    - type: nova
    auth_data:
        # Select your authentication method
        # v3.Password
        username: 
        password:
        domain_name:
        # v3.ApplicationCredential
        application_credential_id:
        application_credential_secret:
        # v3.OidcAccessToken (access_token can instead be the literal token)
        identity_provider:
        access_token: *OPENID