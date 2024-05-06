_© (Thought Machine Group Limited) (2021)_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Team Structure and Ways of Working

## Purpose

Sharing a methodology based on the experience developed in the Inception team to help clients understand at a high-level how to design
a programme for delivering Financial Products. Adapting these structures and processes to the individual client situation should accelerate the ability to quickly deliver high quality Financial Products for deployment to the Vault Platform. This document describes:

- the aims of the Inception team
- key features, roles, and responsibilities of an Inception Build Team
- how the Inception team prioritises, designs, and delivers Financial Products for the Vault Configuration Layer

## Prerequisites

- have received an introduction to Vault and Inception from associated Client Delivery Manager
- familiarity with the basic concepts of how Financial Products can be constructed from Vault Smart Contracts and Workflows

## Further Supporting Documentation

As part of each Inception release package, a set of supporting documentation is provided (in a separate `inception-20YY-VERSION-documentation` folder) which provides an overview of the Inception Library as well as Product Specifications and Integration Guides. These documents are intended for a more general audience but contain useful descriptions of key Vault and Configuration Layer terms and concepts and translate the technical implementation details into business outcomes.

### 1. Key Features, Roles, and Responsibilities of an Inception Build Team

Inception uses a “team of teams” approach to delivery. Teams are formed around a fixed scope for a targeted release date and consist of the right blend of skills to enable:

- Self-organisation of work, roles and responsibilities
- Analysis and refinement of scope
- Creation of “Definition of Ready” user stories
- Technical design and implementation
- Testing and Quality Assurance (QA)
- Documentation

The Build Team contains the following roles:

***Banking Product Specialist (BPS):*** Experienced personnel from the banking industry who are responsible for identifying, describing, and prioritising which Financial Products (e.g. loan, savings account etc.) to build and what features they should include. They provide strategic direction on the Inception Product Library and guidance to the development teams on specifications and implementation. They ensure that what the development teams deliver meets the real-world business needs of a bank.

***Business Analyst (BA):*** Works with the BPS to refine the scope and requirements, breaking down the high-level product feature requests into tasks that Client Engineers can develop against. They define user stories and acceptance criteria, manage the backlog, clarify implementation details, and perform quality assurance after development. They ultimately accept whether features have been completed. Finally, they are responsible for creating the supporting business-level documentation that describes the Financial Product.

***Client Engineer (CE):*** Responsible for the technical implementation of the requirements specified by the BA. Assesses the impact of any technical changes, proposes possible solutions for discussion with the BA and BPS, and writes the code and tests that demonstrate the successful implementation of the required feature.

***Quality Assurance (QA):*** Responsible for testing and assurance that the requirements have been met and there is no regression. Develops manual and automated test strategies for maintaining the overall quality of the library and ensures that the end product meets our customer's expectations.

The Build Teams also rely on dedicated internal technical support for help with managing Vault environments and deploying Configuration Layer content. Another team is also responsible for continuous improvement of the testing framework and toolchain, allowing Build teams to work more quickly whilst ensuring code is thoroughly tested.

### 2. Prioritising, Designing, and Delivering Financial Products

**How do we define scope for the build teams?**

All work being undertaken first passes through a product planning process. In the planning process, ideas and feature requests are reviewed by a panel comprising client delivery, engineering, and product. Prior to submission, the idea must be sized for effort and contain sufficient detail for the panel to assess the idea. Promoted features are then translated to Epics which can then be allocated to Build team boards. The Programme Manager and BPS are responsible for deciding the prioritisation of these features and grouping them in a logical collection.

**Refinement**

Each draft user story should be refined using the 3 amigos approach. The 3 amigos approach brings together different team members. Examples of roles included in this are:

- Business Analyst (representing the ‘Customer’)
- Banking Product Specialist (product subject matter expert)
- Client Engineer (developer)
- Quality Assurance (tester)

Each role will bring a different perspective which will help create a user story that is understood by all.

The aim of the refinement session is to validate the draft user story to ensure that the 3 amigos understand and can deliver it. This is an ongoing process throughout the build to support upcoming sprints. As part of the refinement the user story should be estimated and if it is deemed too large to fit into a single sprint, then a user story may be broken down into further stories.

**Definition of Ready**

A story will be considered ready to be taken into a sprint once it meets the Definition of Ready:

- The story has been estimated
- The story fits into one release
- The delivery of the story has been planned and resource capacity has been assigned
- The story has all the required elements as per the user story guide
- The ‘3 amigos’ are all happy that they understand the story and are committed to delivering

**Delivery of Features**

The Inception testing framework and ways of working allow multiple developers to work on the same Financial Product without causing conflicts. Developers use a mono-repo and then create an individual feature branch for development and testing. Once the changes have been reviewed and accepted, the branch is merged back into the master branch. The workflow is as follows:

1. Get the latest version of the `Master` branch
2. Create a new branch linked to the ticket
3. Write unit, simulation, and end-to-end tests that cover the ticket feature
4. Complete development work to satisfy the tests
5. Commit changes to the development branch
6. Submit the code for peer-review
7. After passing peer-review the code is landed onto `Master`

**Definition of Done**

A story will be considered complete once it meets the Definition of Done:

- The best practice build guidelines has been followed
- All peer review comments have been addressed
- The acceptance criteria specified in the story has been delivered and validated through testing
- The story has been tested in accordance with the test strategy
- All defects have been fixed and retested
- The relevant documentation has been updated

---
