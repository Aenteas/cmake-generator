#include "A/AA/AAA/aaa.h"
#include <gtest/gtest.h>

TEST(myfunctions, add)
{
    GTEST_ASSERT_EQ(mySqrt(9), 3);
}

int main(int argc, char* argv[])
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}