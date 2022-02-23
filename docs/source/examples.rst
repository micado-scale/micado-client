Examples
========

.. note::
    Before you start testing, make sure the cloud credentials are in the correct place.

There are three main use-cases identified for using micado-client.

Use-case 1
----------

A MiCADO node is created with the help of MiCADO client library. The create and destroy methods
are invoked in the same program i.e. storing and retrieving the ``client.micado`` object is not needed.

.. code:: Python

    from micado import MicadoClient

    client = MicadoClient(launcher="openstack", installer="ansible")
    client.micado.create(
        auth_url='yourendpoint',
        project_id='project_id',
        image='image_name or image_id',
        flavor='flavor_name or flavor_id',
        network='network_name or network_id',
        keypair='keypair_name or keypair_id',
        security_group='security_group_name or security_group_id'
        )
    client.applications.list()
    client.micado.destroy()

Use-case 2
----------

A MiCADO node is created with the help of MiCADO client library. The create and destroy methods
are invoked in seperate programs i.e. storing and retrieving the ``client.micado`` object is needed.

.. code:: Python

    from micado import MicadoClient

    client = MicadoClient(launcher="openstack")
    micado_id = client.micado.create(
        auth_url='yourendpoint',
        project_id='project_id',
        image='image_name or image_id',
        flavor='flavor_name or flavor_id',
        network='network_name or network_id',
        keypair='keypair_name or keypair_id',
        security_group='security_group_name or security_group_id'
        )
    client.applications.list()
    << store your micado_id >>
    << exiting... >>
    -------------------------------------------------------------
    << start >>
    ...
    micado_id = << retrieve micado_id >>
    client = MicadoClient(launcher="openstack", installer="ansible")
    client.micado.attach(micado_id=micado_id)
    client.applications.list()
    client.micado.destroy()

Use-case 3
----------

A MiCADO node is created independently from the MiCADO client library. The create and destroy methods
are not invoked since the client library used only for handling the applications.

.. code:: Python

    from micado import MicadoClient
    client = MicadoClient(
        endpoint="https://micado/toscasubmitter/",
        version="v2.0",
        verify=False,
        auth=("ssl_user", "ssl_pass")
        )
    client.applications.list()
