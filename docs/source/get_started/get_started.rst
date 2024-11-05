Get Started
===========

Create a project
----------------

To create a project just provide a name.


.. code-block:: py

    from litrevai import LiteratureReview

    lr = LiteratureReview()
    project = lr.create_project(name='New Project')



Access a project
----------------

.. code-block:: py

    project = lr.projects.get('New Project')

    items = project.items


Create a query
--------------

.. code-block:: py

    prompt = YesNoPrompt(
        question="Is the article about apples?"
    )

    query = project.create_query(
        code='apples',
        prompt=prompt
    )


Run a query
-----------

.. code-block:: py

    query.run()

Alternatively, to run a whole project


.. code-block:: py

    project.run()