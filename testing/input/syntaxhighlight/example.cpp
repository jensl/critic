/* This is a comment
   that spans multiple
   lines. */

/* This one does not. */

// Neither does this. /* Or this. */

#if !defined(FOO)
#  define FOO BAR // Comment
#  define FOO \
  BAR \
  FIE
#endif

int main(int argc, char** argv) {
  double x = float(5.5) + int(3);
  char* s = "this is a string";
  char c = 'c'; // <= that's a character
  return x != 10;
}
