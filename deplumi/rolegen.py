"""
Code to generate AWS IAM data (roles, etc) based on a pile of resources and the
desired actions for each of them.
"""

# * Specific list of actions: Just those actions
# * '*': Everything
# * ...: R/W but not manage (reasonable for an application)

# generate_roles(
#     (BufferBucket, '*'),
#     (WorkQueue, ...),
# )
