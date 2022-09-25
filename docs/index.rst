.. micado-client

MiCADO Client for Python
========================


.. toctree::
   :hidden:
   :maxdepth: 2

   usage
   examples
   api

MiCADO Client Library
*********************

Overview
--------

MiCADO client library extends the MiCADO functionality with MiCADO deployment
capabilities and application management. The library aims to provide a basic API from
Python environment and support the following:

* Deploy MiCADO service
    - Create, Destroy MiCADO node
* Manage application
    - Create, Update, Delete MiCADO applications

Currently, the client library supports OpenStack Nova and CloudBroker interfaces


Roadmap
-------
* Rely on ansible-runner for programmatic installation of MiCADO nodes