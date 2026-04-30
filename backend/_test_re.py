import re
r = re.compile(r'\$\$[^$]*\$\$|\$[^$]*\$|\\(?:begin|end)\{[^}]*\}')
tests = ['$1$', '$textcircled{3}$', '$circledcirc$', 'abc $1$ def', '$$x^2$$', '\\begin{equation}']
for t in tests:
    result = r.sub('', t)
    print(repr(t), '->', repr(result))
print()
# Test with real content from user
real = "如图一山水画，其起承转合关系为： $1$ 起； $2$ 承； $3$ 转； $4$ 结。"
cleaned = r.sub('', real)
print('cleaned:', cleaned)
