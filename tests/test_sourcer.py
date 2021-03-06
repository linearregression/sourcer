import unittest

import collections
import operator
import re

from sourcer import *


Int = Transform(Pattern(r'\d+'), int)
Name = Pattern(r'\w+')
Negation = collections.namedtuple('Negation', 'operator, right')

T = TokenSyntax()
T.Number = r'\d+'

AnyInst = lambda *classes: Where(lambda x: isinstance(x, classes))


class TestSomePotentiallyUsefulStrategies(unittest.TestCase):
    def test_tokenize_indentation(self):
        '''Use Backtrack to recognize indentation tokens.'''
        T = TokenSyntax()
        T.Word = r'\w+'
        T.Newline = r'[\n\r]'

        # If we look back and see a newline, or if we can't backtrack at all,
        # then we know we're at the start of a fresh new line.
        Startline = (Backtrack() >> T.Newline) | Start

        # An indent token is a non-empty sequence of spaces and tabs at the
        # start of a line.
        T.Indent = Right(Startline, Regex(r'[ \t]+'))

        tokens = tokenize(T, '  foo\n    bar\n   baz\nqux')
        contents = [t.content for t in tokens]
        self.assertIsInstance(tokens[0], T.Indent)
        self.assertIsInstance(tokens[3], T.Indent)
        self.assertIsInstance(tokens[6], T.Indent)
        self.assertIsInstance(tokens[1], T.Word)
        self.assertIsInstance(tokens[2], T.Newline)
        self.assertEqual(contents, [
            '  ', 'foo', '\n',
            '    ', 'bar', '\n',
            '   ', 'baz', '\n',
            'qux',
        ])


class TestSimpleExpressions(unittest.TestCase):
    def test_single_token_success(self):
        ans = parse(T.Number, '123')
        self.assertIsInstance(ans, Token)
        self.assertIsInstance(ans, T.Number)
        self.assertEqual(ans.content, '123')

    def test_single_token_failure(self):
        with self.assertRaises(ParseError):
            parse(T.Number, '123X')

    def test_prefix_token_success(self):
        ans = parse_prefix(T.Number, '123ABC')
        self.assertIsInstance(ans, ParseResult)
        token, pos = ans
        self.assertIsInstance(token, Token)
        self.assertIsInstance(token, T.Number)
        self.assertEqual(token.content, '123')
        self.assertEqual(pos, 3)

    def test_prefix_token_failure(self):
        with self.assertRaises(ParseError):
            parse_prefix(T.Number, 'ABC')

    def test_simple_transform(self):
        ans = parse(Int, '123')
        self.assertEqual(ans, 123)

    def test_left_assoc(self):
        Add = ReduceLeft(Int, '+', Int)
        ans = parse(Add, '1+2+3+4')
        self.assertEqual(ans, (((1, '+', 2), '+', 3), '+', 4))

    def test_right_assoc(self):
        Arrow = ReduceRight(Int, '->', Int)
        ans = parse(Arrow, '1->2->3->4')
        self.assertEqual(ans, (1, '->', (2, '->', (3, '->', 4))))

    def test_simple_struct(self):
        class Pair(Struct):
            def parse(self):
                self.left = Int
                self.sep = ','
                self.right = Int

        ans = parse(Pair, '10,20')
        self.assertIsInstance(ans, Pair)
        self.assertEqual(ans.left, 10)
        self.assertEqual(ans.sep, ',')
        self.assertEqual(ans.right, 20)

    def test_two_simple_structs(self):
        class NumberPair(Struct):
            def parse(self):
                self.left = Int
                self.sep = ','
                self.right = Int

        class LetterPair(Struct):
            def parse(self):
                self.left = 'A'
                self.sep = ','
                self.right = 'B'

        Pair = NumberPair | LetterPair
        TwoPairs = (Pair, ',', Pair)
        ans1, comma, ans2 = parse(TwoPairs, 'A,B,100,200')
        self.assertIsInstance(ans1, LetterPair)
        self.assertEqual((ans1.left, ans1.right), ('A', 'B'))
        self.assertEqual(comma, ',')
        self.assertIsInstance(ans2, NumberPair)
        self.assertEqual((ans2.left, ans2.right), (100, 200))

    def test_simple_alt_sequence(self):
        Nums = Alt(Int, ',')
        ans = parse(Nums, '1,2,3,4')
        self.assertEqual(ans, [1,2,3,4])

    def test_opt_term_present(self):
        Seq = ('A', Opt('B'))
        ans = parse(Seq, 'AB')
        self.assertEqual(ans, ('A', 'B'))

    def test_opt_term_missing_front(self):
        Seq = (Opt('A'), 'B')
        ans = parse(Seq, 'B')
        self.assertEqual(ans, (None, 'B'))

    def test_opt_term_missing_middle(self):
        Seq = ('A', Opt('B'), 'C')
        ans = parse(Seq, 'AC')
        self.assertEqual(ans, ('A', None, 'C'))

    def test_opt_term_missing_end(self):
        Seq = ('A', Opt('B'))
        ans = parse(Seq, 'A')
        self.assertEqual(ans, ('A', None))

    def test_opt_operator(self):
        Seq = ('A', ~Right('A', 'B'))
        ans1 = parse(Seq, 'AAB')
        ans2 = parse(Seq, 'A')
        self.assertEqual(ans1, ('A', 'B'))
        self.assertEqual(ans2, ('A', None))

    def test_left_term(self):
        T = Left('A', 'B')
        ans = parse(T, 'AB')
        self.assertEqual(ans, 'A')

    def test_left_term_with_operator(self):
        T = 'A' << Opt('B')
        ans = parse(T, 'AB')
        self.assertEqual(ans, 'A')

    def test_right_term(self):
        T = Right('A', 'B')
        ans = parse(T, 'AB')
        self.assertEqual(ans, 'B')

    def test_right_term_with_operatorself(self):
        T = Opt('A') >> 'B'
        ans = parse(T, 'AB')
        self.assertEqual(ans, 'B')

    def test_require_success(self):
        T = Require(List('A'), lambda ans: len(ans) > 2)
        ans = parse(T, 'AAA')
        self.assertEqual(ans, list('AAA'))

    def test_require_failure(self):
        T = Require(List('A'), lambda ans: len(ans) > 2)
        with self.assertRaises(ParseError):
            ans = parse(T, 'AA')

    def test_ordered_choice_first(self):
        T = (Or('A', 'AB'), 'B')
        ans = parse(T, 'AB')
        self.assertEqual(ans, ('A', 'B'))

    def test_ordered_choice_second(self):
        T = Or('A', 'B')
        ans = parse(T, 'B')
        self.assertEqual(ans, 'B')

    def test_ordered_choice_third(self):
        T = reduce(Or, 'ABC')
        ans = parse(T, 'C')
        self.assertEqual(ans, 'C')

    def test_and_operator(self):
        Vowel = reduce(Or, 'AEIOU')
        Prefix = 'ABCD' & Vowel
        T = (Prefix, Any)
        ans = parse(T, 'ABCDE')
        self.assertEqual(ans, ('ABCD', 'E'))
        with self.assertRaises(ParseError):
            parse(T, 'ABCD')

    def test_expect_term(self):
        T = (Expect('A'), 'A')
        ans = parse(T, 'A')
        self.assertEqual(ans, ('A', 'A'))

    def test_empty_alt_term(self):
        T = '(' >> Alt('A', ',') << ')'
        ans = parse(T, '()')
        self.assertEqual(ans, [])

    def test_left_assoc_struct(self):
        class Dot(LeftAssoc):
            def parse(self):
                self.left = Name
                self.op = '.'
                self.right = Name
            def __str__(self):
                return '(%s).%s' % (self.left, self.right)
        ans = parse(Dot, 'foo.bar.baz.qux')
        self.assertIsInstance(ans, Dot)
        self.assertEqual(ans.right, 'qux')
        self.assertEqual(ans.left.right, 'baz')
        self.assertEqual(ans.left.left.right, 'bar')
        self.assertEqual(ans.left.left.left, 'foo')
        self.assertEqual(str(ans), '(((foo).bar).baz).qux')

    def test_right_assoc_struct(self):
        class Arrow(RightAssoc):
            def parse(self):
                self.left = Name
                self.op = ' -> '
                self.right = Name
            def __str__(self):
                return '%s -> (%s)' % (self.left, self.right)
        ans = parse(Arrow, 'a -> b -> c -> d')
        self.assertIsInstance(ans, Arrow)
        self.assertEqual(ans.left, 'a')
        self.assertEqual(ans.right.left, 'b')
        self.assertEqual(ans.right.right.left, 'c')
        self.assertEqual(ans.right.right.right, 'd')
        self.assertEqual(str(ans), 'a -> (b -> (c -> (d)))')

    def test_simple_where_term(self):
        vowels = 'aeiou'
        Vowel = Where(lambda x: x in vowels)
        Consonant = Where(lambda x: x not in vowels)
        Pattern = (Consonant, Vowel, Consonant)
        ans = parse(Pattern, 'bar')
        self.assertEqual(ans, tuple('bar'))
        with self.assertRaises(ParseError):
            parse(Pattern, 'foo')

    def test_list_of_numbers_as_source(self):
        Odd = Literal(1) | Literal(3)
        Even = Literal(2) | Literal(4)
        Pair = (Odd, Even)
        Pairs = List(Pair)
        ans = parse(Pairs, [1, 2, 3, 4, 3, 2])
        self.assertEqual(ans, [(1, 2), (3, 4), (3, 2)])

    def test_mixed_list_of_values_as_source(self):
        Null = Literal(None)
        Str = AnyInst(basestring)
        Int = AnyInst(int)
        Empty = Literal([])
        Intro = Literal([0, 0, 0])
        Body = (Intro, Empty, Int, Str, Null)
        source = [[0, 0, 0], [], 15, "ok bye", None]
        ans = parse(Body, source)
        self.assertEqual(ans, tuple(source))
        bad_source = [[0, 0, 1]] + source[1:]
        with self.assertRaises(ParseError):
            parse(Body, bad_source)

    def test_any_inst_with_multiple_classes(self):
        Str = AnyInst(basestring)
        Num = AnyInst(int, float)
        Nums = (Num, Num, Str)
        source = [0.0, 10, 'ok']
        ans = parse(Nums, source)
        self.assertEqual(ans, tuple(source))
        with self.assertRaises(ParseError):
            parse(Nums, [200, 'ok', 100])

    def test_bind_expression(self):
        zs = Bind(Int, lambda count: 'z' * count)
        ans = parse(zs, '4zzzz')
        self.assertEqual(ans, 'zzzz')
        with self.assertRaises(ParseError):
            parse(zs, '4zzz')

    def test_parse_empty_string(self):
        seq = ('', 'foo', '', 'bar', '')
        ans = parse(seq, 'foobar')
        self.assertEqual(ans, seq)
        with self.assertRaises(ParseError):
            parse(seq, 'foo bar')
        alt = parse('', '')
        self.assertEqual(alt, '')

    def test_default_literal(self):
        msg = object()
        seq = (0, 1, 2, msg)
        ans = parse(seq, [0, 1, 2, msg])
        self.assertEqual(ans, seq)
        with self.assertRaises(ParseError):
            parse(seq, [1, 2, msg])

    def test_none_is_return_none_not_literal_none(self):
        # The expression compiler interprets ``None`` as ``Return(None)`` as
        # opposed to ``Literal(None)``.
        seq1 = ('foo', None, 'bar')
        ans1 = parse(seq1, 'foobar')
        self.assertEqual(ans1, seq1)
        seq2 = (Literal('foo'), None, Literal('bar'))
        ans2 = parse(seq2, ['foo', 'bar'])
        self.assertEqual(ans2, seq1)
        with self.assertRaises(ParseError):
            parse(seq2, ['foo', None, 'bar'])
        seq3 = (Literal('foo'), Literal(None), Literal('bar'))
        ans3 = parse(seq3, ['foo', None, 'bar'])
        self.assertEqual(ans3, seq1)


class TestOperatorPrecedenceTable(unittest.TestCase):
    def grammar(self):
        Parens = '(' >> ForwardRef(lambda: Expr) << ')'
        Expr = OperatorPrecedence(
            Int | Parens,
            Prefix('+', '-'),
            Postfix('%'),
            InfixRight('^'),
            InfixLeft('*', '/'),
            InfixLeft('+', '-'),
        )
        return Expr

    def evaluate(self, obj):
        if isinstance(obj, int):
            return obj
        evaluate = self.evaluate
        assert isinstance(obj, Operation)
        if obj.operator == '+' and obj.left is None:
            return evaluate(obj.right)
        if obj.operator == '-' and obj.left is None:
            return -evaluate(obj.right)
        if obj.operator == '%':
            assert obj.right is None
            return evaluate(obj.left) / 100.0
        operators = {
            '^': operator.pow,
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
            '/': operator.div,
        }
        left = evaluate(obj.left)
        right = evaluate(obj.right)
        func = operators[obj.operator]
        return func(left, right)

    def parse_and_evaluate(self, source):
        ans = parse(self.grammar(), source)
        return self.evaluate(ans)

    def test_compatible_expressions(self):
        testcases = [
            '1',
            '1+2',
            '1+2*3',
            '+1++2',
            '+-+-1++--2',
            '--1---2----3',
            '1+1+1+1',
            '1+2+3+4*5*6',
            '1+2+3*4-(5+6)/7',
            '(((1)))+(2)',
            '8/4/2',
            '(1+2)*3',
            '1+(2*3)',
            '(1+((2*(-3))/4))-5',
        ]
        for src in testcases:
            ans = self.parse_and_evaluate(src)
            self.assertEqual(ans, eval(src))

    def test_incompatible_expressions(self):
        testcases = {
            '2^3^4': '2**(3**4)',
            '1+2%': '1+(2/100.0)',
            '1+205%%*3': '1+(205/100.0/100.0)*3',
            '5^200%': '5**(200/100.0)',
        }
        for src, expected in testcases.iteritems():
            ans = self.parse_and_evaluate(src)
            self.assertEqual(ans, eval(expected))


class TestArithmeticExpressions(unittest.TestCase):
    def grammar(self):
        F = ForwardRef(lambda: Factor)
        E = ForwardRef(lambda: Expr)
        Parens = '(' >> E << ')'
        Negate = Transform(('-', F), lambda p: Negation(*p))
        Factor = Int | Parens | Negate
        Term = ReduceLeft(Factor, Or('*', '/'), Factor) | Factor
        Expr = ReduceLeft(Term, Or('+', '-'), Term) | Term
        return Expr

    def parse(self, source):
        return parse(self.grammar(), source)

    def test_ints(self):
        for i in range(10):
            ans = self.parse(str(i))
            self.assertEqual(ans, i)

    def test_int_in_parens(self):
        ans = self.parse('(100)')
        self.assertEqual(ans, 100)

    def test_many_parens(self):
        for i in range(10):
            prefix = '(' * i
            suffix = ')' * i
            ans = self.parse('%s%s%s' % (prefix, i, suffix))
            self.assertEqual(ans, i)

    def test_simple_negation(self):
        ans = self.parse('-50')
        self.assertEqual(ans, Negation('-', 50))

    def test_double_negation(self):
        ans = self.parse('--100')
        self.assertEqual(ans, Negation('-', Negation('-', 100)))

    def test_subtract_negative(self):
        ans = self.parse('1--2')
        self.assertEqual(ans, (1, '-', Negation('-', 2)))

    def test_simple_precedence(self):
        ans = self.parse('1+2*3')
        self.assertEqual(ans, (1, '+', (2, '*', 3)))

    def test_simple_precedence_with_parens(self):
        ans = self.parse('(1+2)*3')
        self.assertEqual(ans, ((1, '+', 2), '*', 3))

    def test_compound_term(self):
        t1 = self.parse('1+2*-3/4-5')
        t2 = self.parse('(1+((2*(-3))/4))-5')
        self.assertEqual(t1, t2)


class TestCalculator(unittest.TestCase):
    def grammar(self):
        F = ForwardRef(lambda: Factor)
        E = ForwardRef(lambda: Expr)
        Parens = '(' >> E << ')'
        Negate = Transform(Right('-', F), lambda x: -x)
        Factor = Int | Parens | Negate
        operators = {
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
            '/': operator.div,
        }
        def evaluate(left, op, right):
            return operators[op](left, right)
        def binop(left, op, right):
            return ReduceLeft(left, op, right, evaluate)
        Term = binop(Factor, Or('*', '/'), Factor) | Factor
        Expr = binop(Term, Or('+', '-'), Term) | Term
        return Expr

    def test_expressions(self):
        grammar = self.grammar()
        expressions = [
            '1',
            '1+2',
            '1+2*3',
            '--1---2----3',
            '1+1+1+1',
            '1+2+3+4*5*6',
            '1+2+3*4-(5+6)/7',
            '(((1)))+(2)',
            '8/4/2',
        ]
        for expression in expressions:
            ans = parse(grammar, expression)
            self.assertEqual(ans, eval(expression))


class TestEagerLambdaCalculus(unittest.TestCase):
    def grammar(self):
        Parens = '(' >> ForwardRef(lambda: Expr) << ')'

        class Identifier(Struct):
            def parse(self):
                self.name = Name

            def __repr__(self):
                return self.name

            def evaluate(self, env):
                return env.get(self.name, self.name)

        class Abstraction(Struct):
            def parse(self):
                self.symbol = '\\'
                self.parameter = Name
                self.separator = '.'
                self.space = Opt(' ')
                self.body = Expr

            def __repr__(self):
                return '(\\%s. %r)' % (self.parameter, self.body)

            def evaluate(self, env):
                def callback(arg):
                    child = env.copy()
                    child[self.parameter] = arg
                    return self.body.evaluate(child)
                return callback

        class Application(LeftAssoc):
            def parse(self):
                self.left = Operand
                self.operator = ' '
                self.right = Operand

            def __repr__(self):
                return '%r %r' % (self.left, self.right)

            def evaluate(self, env):
                left = self.left.evaluate(env)
                right = self.right.evaluate(env)
                return left(right)

        Operand = Parens | Abstraction | Identifier
        Expr = Application | Operand
        return Expr

    def test_expressions(self):
        grammar = self.grammar()
        testcases = [
            ('x', 'x'),
            ('(x)', 'x'),
            (r'(\x. x) y', 'y'),
            (r'(\x. \y. x) a b', 'a'),
            (r'(\x. \y. y) a b', 'b'),
            (r'(\x. \y. x y) (\x. z) b', 'z'),
            (r'(\x. \y. y x) z (\x. x)', 'z'),
            (r'(\x. \y. \t. t x y) a b (\x. \y. x)', 'a'),
            (r'(\x. \y. \t. t x y) a b (\x. \y. y)', 'b'),
        ]
        for (test, expectation) in testcases:
            ast = parse(grammar, test)
            ans = ast.evaluate({})
            self.assertEqual(ans, expectation)


class TestTokens(unittest.TestCase):
    def tokenize(self, tokenizer, source):
        tokens = tokenize(tokenizer, source)
        return [t.content for t in tokens]

    def test_numbers_and_spaces(self):
        T = TokenSyntax()
        T.Word = r'\w+'
        T.Space = r'\s+'
        ans = self.tokenize(T, 'A B C')
        self.assertEqual(ans, list('A B C'))

    def test_numbers_and_spaces_with_regexes(self):
        T = TokenSyntax()
        T.Word = Regex(r'\w+')
        T.Space = re.compile(r'\s+')
        ans = self.tokenize(T, 'A B C')
        self.assertEqual(ans, list('A B C'))

    def test_skip_spaces(self):
        T = TokenSyntax()
        T.Number = r'\d+'
        T.Space = Skip(r'\s+')
        ans = self.tokenize(T, '1 2 3')
        self.assertEqual(ans, list('123'))

    def test_token_types(self):
        T = TokenSyntax()
        T.Number = r'\d+'
        T.Space = Skip(r'\s+')
        tokens = tokenize(T, '1 2 3')
        self.assertIsInstance(tokens, list)
        self.assertEqual(len(tokens), 3)
        for index, token in enumerate(tokens):
            self.assertIsInstance(token, T.Number)
            self.assertEqual(token.content, str(index + 1))

    def test_one_char_in_string(self):
        T = TokenSyntax()
        T.Symbol = AnyChar('(.*[;,])?')
        sample = '[]().*;;'
        ans = self.tokenize(T, sample)
        self.assertEqual(ans, list(sample))

    def test_init_style(self):
        class FooTokens(TokenSyntax):
            def __init__(self):
                self.Space = Skip(r'\s+')
                self.Word = r'[a-zA-Z_][a-zA-Z_0-9]*'
                self.Symbol = Skip(AnyChar(',.;'))
        sample = 'This is a test, everybody.'
        ans = self.tokenize(FooTokens(), sample)
        self.assertEqual(ans, ['This', 'is', 'a', 'test', 'everybody'])

    def test_tokenize_and_parse(self):
        class CalcTokens(TokenSyntax):
            def __init__(self):
                self.Space = Skip(r'\s+')
                self.Number = r'\d+'
                self.Operator = AnyChar('+*-/')
        class Factor(LeftAssoc):
            def parse(self):
                self.left = Operand
                self.operator = Or('/', '*')
                self.right = Operand
        class Term(LeftAssoc):
            def parse(self):
                self.left = Factor | Operand
                self.operator = Or('+', '-')
                self.right = Factor | Operand
        T = CalcTokens()
        Operand = T.Number
        sample = '1 + 2 * 3 - 4'
        ans = tokenize_and_parse(T, Term, sample)
        self.assertIsInstance(ans, Term)


class TestSignificantIndentation(unittest.TestCase):
    def test_greedy_body(self):
        Word = Pattern(r'\w+')
        # SHOULD: Consider implementing __eq__ and __hash__ in the Struct
        # superclass. Also, consider providing a constructor that accepts
        # keyword arguments. (Also, consider implementing __repr__, too.)
        class Command(Struct):
            def parse(self):
                self.message = 'print ' >> Word << '\n'
            def __eq__(self, other):
                return (isinstance(other, Command)
                    and self.message == other.message)
        class Loop(Struct):
            def parse(self):
                self.count = 'loop ' >> Int << ' times\n'
                self.body = Block
            def __eq__(self, other):
                return (isinstance(other, Loop)
                    and self.count == other.count
                    and self.body == other.body)
        Statement = Command | Loop
        def IndentedStatement(indent):
            return Right(indent, Statement)
        def IndentedBlock(indent):
            return Some(IndentedStatement(indent))
        Indent = Pattern('[ \t]*')
        Block = Bind(Expect(Indent), IndentedBlock)
        Program = '\n' >> Block << Indent
        ans1 = parse(Program, '''
            print alfa
            print bravo
            loop 5 times
                print charlie
                print delta
                loop 2 times
                    print echo
                    print foxtrot
                print golf
                print hotel
            print india
        ''')
        def cmd(message):
            ans = Command()
            ans.message = message
            return ans
        def loop(count, body):
            ans = Loop()
            ans.count = count
            ans.body = body
            return ans
        self.assertEqual(ans1, [
            cmd('alfa'),
            cmd('bravo'),
            loop(5, [
                cmd('charlie'),
                cmd('delta'),
                loop(2, [
                    cmd('echo'),
                    cmd('foxtrot'),
                ]),
                cmd('golf'),
                cmd('hotel'),
            ]),
            cmd('india'),
        ])
        # The disadvantage with this approach is that
        # it doesn't fail when the body isn't indented.
        ans2 = parse(Program, '''
            print juliett
            loop 10 times
            print kilo
            print lima
        ''')
        self.assertEqual(ans2, [
            cmd('juliett'),
            loop(10, [
                cmd('kilo'),
                cmd('lima'),
            ]),
        ])
        with self.assertRaises(ParseError):
            parse(Program, '''
                print mike
                    print november
            ''')

    def test_careful_body(self):
        Word = Pattern(r'\w+')
        class Command(Struct):
            def parse(self):
                self.message = 'print ' >> Word << '\n'
            def __eq__(self, other):
                return (isinstance(other, Command)
                    and self.message == other.message)
        # SHOULD: Consider making a data-dependent struct.
        # Alternately, consider making the bindings available
        # to other rules.
        def Loop(indent):
            class LoopClass(Struct):
                def parse(self):
                    self.count = 'loop ' >> Int << ' times\n'
                    self.body = Opt(Block(indent))
                def __eq__(self, other):
                    return (hasattr(other, 'count')
                        and self.count == other.count
                        and self.body == other.body)
            return LoopClass
        def IndentedStatement(indent):
            return Right(indent, Command | Loop(indent))
        def Block(current):
            indent = Require(Expect(Indent), lambda i: len(current) < len(i))
            return Bind(indent, lambda i: List(IndentedStatement(i)))
        Indent = Pattern(' *')
        Program = '\n' >> Block('') << Indent
        def cmd(message):
            ans = Command()
            ans.message = message
            return ans
        def loop(count, body):
            ans = Loop('')()
            ans.count = count
            ans.body = body
            return ans
        ans = parse(Program, '''
            print alfa
            loop 10 times
            print bravo
            print charlie
        ''')
        self.assertEqual(ans, [
            cmd('alfa'),
            loop(10, None),
            cmd('bravo'),
            cmd('charlie'),
        ])
        with self.assertRaises(ParseError):
            parse(Program, '''
                print foo
                loop 20 times
            print bar
                print baz
            ''')

    def test_replace_method(self):
        class Foobar(Struct):
            def parse(self):
                self.foo = 'foo'
                self.sep = ':'
                self.bar = 'bar'

        raw = parse(Foobar, 'foo:bar')
        self.assertIsInstance(raw, Foobar)
        self.assertEqual(raw.foo, 'foo')
        self.assertEqual(raw.sep, ':')
        self.assertEqual(raw.bar, 'bar')

        cooked = raw._replace(foo='FOO', bar='BAR')
        self.assertIsInstance(cooked, Foobar)
        self.assertEqual(cooked.foo, 'FOO')
        self.assertEqual(cooked.sep, ':')
        self.assertEqual(cooked.bar, 'BAR')


class RegressionTests(unittest.TestCase):
    def test_stack_depth(self):
        test = ('(1+' * 100) + '1' + (')' * 100)
        Parens = '(' >> ForwardRef(lambda: Add) << ')'
        Term = Parens | '1'
        Add = (Term, '+', Term) | Term
        ans = parse(Add, test)
        self.assertIsInstance(ans, tuple)
        self.assertEqual(ans[0], '1')
        self.assertEqual(ans[1], '+')

    def test_infinite_list(self):
        InfLoop = List('')
        ans = parse_prefix(InfLoop, 'abc')
        self.assertIsInstance(ans, ParseResult)
        self.assertEqual(ans.value, [])
        self.assertEqual(ans.pos, 0)

    def test_infinite_operators(self):
        InfOp = OperatorPrecedence(Int, Prefix(''))
        ans = parse(InfOp, '123')
        self.assertEqual(ans, 123)


class TestPerformanceWithManyOperators(unittest.TestCase):
    def grammar(self):
        Parens = '(' >> ForwardRef(lambda: Expr) << ')'
        Var = Pattern(r'[A-Z]')
        Expr = OperatorPrecedence(
            Var | Int | Parens,
            Prefix('+', '-'),
            Postfix('%'),
            InfixRight('^'),
            InfixLeft('*', '/'),
            InfixLeft('+', '-'),
            InfixLeft(' by '),
            InfixLeft(' to '),
            InfixLeft('<', '<=', '>=', '>'),
            InfixLeft('==', '!='),
            InfixLeft(' and '),
            InfixLeft(' or '),
            InfixRight(' implies ', '->'),
            InfixLeft(' foo '),
            InfixLeft(' bar '),
            InfixLeft(' baz '),
            InfixLeft(' fiz '),
            InfixLeft(' buz '),
            InfixLeft(' zim '),
            InfixLeft(' zam '),
        )
        return Expr

    def test_long_expression(self):
        source = '++1+2--3*4^5->A->B implies 1<2 and -X to +Y by --Z%'
        ans = parse(self.grammar(), source)
        self.assertIsInstance(ans, Operation)


if __name__ == '__main__':
    unittest.main()
