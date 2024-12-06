Get Started
===========

Create a project
----------------

To create a project just provide a name.


.. code-block:: py

    from litrevai import LiteratureReview

    lr = LiteratureReview()
    project = lr.create_project(name='New Project')



Import items from Zotero
------------------------

.. code-block:: py

    lr.import_zotero()


Access a project
----------------

.. code-block:: py

    project = lr.projects.get('New Project')

    project.add_items(lr.items)

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


Configure an inference model
----------------------------

.. code-block:: py

    model = OpenAIModel()

    lr.set_llm(model)


Run a query
-----------

.. code-block:: py

    query.run()

Alternatively, to run a whole project


.. code-block:: py

    project.run()


Create a topic model
--------------------

.. code-block:: py

    topic_model = query.create_topic_model(min_cluster_size=5)

    topic_model.visualize_topic_distribution()